"""
M-Pesa Daraja API – STK Push (Lipa Na M-Pesa Online).
Uses credentials from settings (Consumer Key/Secret configured there).
"""
import base64
import json
import logging
from datetime import datetime
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Daraja base URLs (Safaricom developer portal)
SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


def _base_url() -> str:
    return SANDBOX_BASE if getattr(settings, "MPESA_ENV", "sandbox") == "sandbox" else PRODUCTION_BASE


def diagnose_access_token_issue() -> dict[str, Any]:
    """
    Diagnostic function to help identify access token issues.
    Returns a dict with diagnostic information.
    """
    diagnostics = {
        "environment": getattr(settings, "MPESA_ENV", "sandbox"),
        "base_url": _base_url(),
        "consumer_key_set": bool(getattr(settings, "MPESA_CONSUMER_KEY", "")),
        "consumer_secret_set": bool(getattr(settings, "MPESA_CONSUMER_SECRET", "")),
        "consumer_key_length": len(str(getattr(settings, "MPESA_CONSUMER_KEY", ""))),
        "consumer_secret_length": len(str(getattr(settings, "MPESA_CONSUMER_SECRET", ""))),
        "issues": []
    }
    
    # Check for common issues
    if not diagnostics["consumer_key_set"]:
        diagnostics["issues"].append("MPESA_CONSUMER_KEY is not set")
    if not diagnostics["consumer_secret_set"]:
        diagnostics["issues"].append("MPESA_CONSUMER_SECRET is not set")
    
    if diagnostics["consumer_key_length"] < 10:
        diagnostics["issues"].append(f"MPESA_CONSUMER_KEY appears too short ({diagnostics['consumer_key_length']} chars)")
    if diagnostics["consumer_secret_length"] < 10:
        diagnostics["issues"].append(f"MPESA_CONSUMER_SECRET appears too short ({diagnostics['consumer_secret_length']} chars)")
    
    # Test network connectivity
    try:
        test_resp = requests.get(f"{diagnostics['base_url']}/oauth/v1/generate?grant_type=client_credentials", timeout=5)
        diagnostics["network_reachable"] = True
        diagnostics["test_status_code"] = test_resp.status_code
    except requests.exceptions.Timeout:
        diagnostics["network_reachable"] = False
        diagnostics["issues"].append("Network timeout - cannot reach Daraja API")
    except requests.exceptions.ConnectionError:
        diagnostics["network_reachable"] = False
        diagnostics["issues"].append("Connection error - cannot reach Daraja API")
    except Exception as e:
        diagnostics["network_reachable"] = False
        diagnostics["issues"].append(f"Network test failed: {str(e)}")
    
    return diagnostics


def get_access_token() -> str | None:
    """
    Get OAuth access token using Consumer Key and Consumer Secret.
    Returns the access_token string or None on failure.
    """
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    key = str(getattr(settings, "MPESA_CONSUMER_KEY", "")).strip()
    secret = str(getattr(settings, "MPESA_CONSUMER_SECRET", "")).strip()
    
    # Validate credentials are set
    if not key or not secret:
        logger.error("MPESA_CONSUMER_KEY or MPESA_CONSUMER_SECRET not set in settings")
        logger.error("MPESA_CONSUMER_KEY present: %s", bool(key))
        logger.error("MPESA_CONSUMER_SECRET present: %s", bool(secret))
        return None
    
    # Validate key format (should not be empty after stripping)
    if len(key) < 10 or len(secret) < 10:
        logger.error("MPESA credentials appear to be too short or invalid")
        logger.error("Key length: %d, Secret length: %d", len(key), len(secret))
        return None
    
    # Create Basic Auth header
    try:
        auth_string = f"{key}:{secret}"
        auth_bytes = auth_string.encode('utf-8')
        auth = base64.b64encode(auth_bytes).decode('utf-8')
    except Exception as e:
        logger.exception("Failed to encode credentials for Basic Auth: %s", e)
        return None
    
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }
    
    # Log request details (without exposing secrets)
    logger.info("Requesting access token from: %s", url)
    logger.debug("Using MPESA_ENV: %s", getattr(settings, "MPESA_ENV", "sandbox"))
    logger.debug("Consumer Key (first 10 chars): %s...", key[:10] if len(key) > 10 else key)
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        
        # Log response status
        logger.info("Access token response status: %s", resp.status_code)
        
        # Handle non-200 status codes with detailed error info
        if resp.status_code != 200:
            error_text = resp.text
            logger.error("Access token HTTP error %s", resp.status_code)
            logger.error("Response headers: %s", dict(resp.headers))
            logger.error("Response body: %s", error_text)
            
            # Try to parse error response
            try:
                error_data = resp.json()
                error_msg = error_data.get("error_description") or error_data.get("error") or error_data.get("message", error_text)
                logger.error("Parsed error message: %s", error_msg)
            except:
                logger.error("Could not parse error response as JSON")
            
            # Common error codes and their meanings
            if resp.status_code == 401:
                logger.error("Authentication failed - check your Consumer Key and Consumer Secret")
            elif resp.status_code == 403:
                logger.error("Access forbidden - check your API permissions on Daraja portal")
            elif resp.status_code == 404:
                logger.error("Endpoint not found - check MPESA_ENV setting (sandbox/production)")
            elif resp.status_code >= 500:
                logger.error("Daraja server error - try again later")
            
            return None
        
        # Parse JSON response
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as json_err:
            logger.error("Access token invalid JSON response")
            logger.error("Response status: %s", resp.status_code)
            logger.error("Response headers: %s", dict(resp.headers))
            logger.error("Response body: %s", resp.text)
            logger.error("JSON decode error: %s", str(json_err))
            return None
        
        # Check for error in response body
        if "error" in data:
            error_type = data.get("error", "unknown")
            error_desc = data.get("error_description", data.get("errorMessage", "Unknown error"))
            logger.error("Access token API error: %s - %s", error_type, error_desc)
            return None
        
        # Extract access token
        access_token = data.get("access_token")
        if not access_token:
            error_msg = data.get("error_description") or data.get("error", "Unknown error")
            logger.error("Access token not found in response")
            logger.error("Response data: %s", json.dumps(data, indent=2))
            logger.error("Error message: %s", error_msg)
            return None
        
        # Validate token format (should be a non-empty string)
        if not isinstance(access_token, str) or len(access_token) < 10:
            logger.error("Access token format appears invalid (too short)")
            logger.error("Token length: %d", len(access_token) if isinstance(access_token, str) else 0)
            return None
        
        logger.info("Access token retrieved successfully (length: %d)", len(access_token))
        return access_token
        
    except requests.exceptions.Timeout:
        logger.error("Access token request timeout after 30 seconds")
        logger.error("This could indicate network issues or Daraja API being slow")
        return None
    except requests.exceptions.SSLError as ssl_err:
        logger.exception("SSL/TLS error when connecting to Daraja API: %s", ssl_err)
        logger.error("This might indicate certificate or network configuration issues")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logger.exception("Connection error when connecting to Daraja API: %s", conn_err)
        logger.error("Check your internet connection and Daraja API availability")
        return None
    except requests.exceptions.RequestException as e:
        logger.exception("Access token network error: %s", e)
        logger.error("Request exception type: %s", type(e).__name__)
        return None
    except Exception as e:
        logger.exception("Unexpected error in get_access_token: %s", e)
        logger.error("Error type: %s", type(e).__name__)
        return None


def stk_push(phone_number: str, amount: int, account_reference: str, callback_url: str) -> dict[str, Any]:
    """
    Initiate Lipa Na M-Pesa Online (STK Push).
    phone_number: full format e.g. 254712345678
    amount: integer (KES)
    account_reference: short reference (e.g. "ZaoConnect" or order id)
    callback_url: full URL for Daraja to POST the result (must be publicly reachable).

    Returns dict with keys: success (bool), checkout_request_id (str or None), error_message (str).
    """
    token = get_access_token()
    if not token:
        # Run diagnostics to provide helpful error message
        diag = diagnose_access_token_issue()
        error_msg = "Failed to get access token"
        if diag["issues"]:
            error_msg += f". Issues found: {', '.join(diag['issues'])}"
        else:
            error_msg += ". Check your MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET in settings.py"
        logger.error("STK Push aborted: %s", error_msg)
        return {"success": False, "checkout_request_id": None, "error_message": error_msg}

    # Validate phone number format (should be 12 digits starting with 254)
    phone_number = phone_number.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not phone_number.isdigit() or len(phone_number) != 12 or not phone_number.startswith("254"):
        return {
            "success": False,
            "checkout_request_id": None,
            "error_message": f"Invalid phone number format. Expected 12 digits starting with 254, got: {phone_number}"
        }
    
    # Validate amount
    if amount < 1:
        return {
            "success": False,
            "checkout_request_id": None,
            "error_message": "Amount must be at least 1 KES"
        }
    
    shortcode = str(getattr(settings, "MPESA_SHORTCODE", "174379")).strip()
    passkey = str(getattr(settings, "MPESA_PASSKEY", "")).strip()
    if not passkey:
        return {"success": False, "checkout_request_id": None, "error_message": "MPESA_PASSKEY not set"}

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_str = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode()

    url = f"{_base_url()}/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(round(amount)),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference[:12],
        "TransactionDesc": "Order payment",
    }
    
    # Log payload (without sensitive data) for debugging
    logger.info("STK Push request: Phone=%s, Amount=%s, Shortcode=%s", phone_number, amount, shortcode)
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # Log the raw response for debugging
        logger.info("STK Push response status: %s", resp.status_code)
        logger.info("STK Push response body: %s", resp.text)
        
        # Handle non-200 status codes
        if resp.status_code != 200:
            error_text = resp.text
            logger.error("STK Push HTTP error %s: %s", resp.status_code, error_text)
            return {
                "success": False,
                "checkout_request_id": None,
                "error_message": f"HTTP {resp.status_code}: {error_text[:200]}"
            }
        
        # Parse JSON response
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as json_err:
            logger.error("STK Push invalid JSON response: %s", resp.text)
            return {
                "success": False,
                "checkout_request_id": None,
                "error_message": f"Invalid JSON response: {str(json_err)}"
            }
        
        # Check for error in response
        if "errorCode" in data or "errorMessage" in data:
            error_code = data.get("errorCode", "Unknown")
            error_msg = data.get("errorMessage", data.get("error", {}).get("message", "Unknown error"))
            logger.warning("STK Push API error: Code=%s, Message=%s", error_code, error_msg)
            return {
                "success": False,
                "checkout_request_id": None,
                "error_message": f"Error {error_code}: {error_msg}"
            }
        
        # Check ResponseCode (Daraja uses "0" for success)
        response_code = str(data.get("ResponseCode", "")).strip()
        checkout_request_id = (data.get("CheckoutRequestID") or "").strip()
        
        if response_code == "0" and checkout_request_id:
            logger.info("STK Push successful: CheckoutRequestID=%s", checkout_request_id)
            return {
                "success": True,
                "checkout_request_id": checkout_request_id,
                "error_message": "",
                "merchant_request_id": data.get("MerchantRequestID", ""),
                "customer_message": data.get("CustomerMessage", "")
            }
        else:
            # ResponseCode is not "0" or missing CheckoutRequestID
            response_desc = data.get("ResponseDescription", "Unknown error")
            logger.warning("STK Push failed: ResponseCode=%s, Description=%s", response_code, response_desc)
            return {
                "success": False,
                "checkout_request_id": checkout_request_id if checkout_request_id else None,
                "error_message": f"ResponseCode {response_code}: {response_desc}"
            }
            
    except requests.exceptions.Timeout:
        logger.error("STK Push request timeout")
        return {
            "success": False,
            "checkout_request_id": None,
            "error_message": "Request timeout - please try again"
        }
    except requests.exceptions.RequestException as e:
        logger.exception("STK Push network error: %s", e)
        return {
            "success": False,
            "checkout_request_id": None,
            "error_message": f"Network error: {str(e)}"
        }
    except Exception as e:
        logger.exception("STK Push unexpected error: %s", e)
        return {
            "success": False,
            "checkout_request_id": None,
            "error_message": f"Unexpected error: {str(e)}"
        }
