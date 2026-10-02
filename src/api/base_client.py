"""
Base HTTP client module with error handling, session management, and timeouts.
"""
from typing import Any, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ResourceNotFoundError(APIError):
    """Raised when an API returns 404 (e.g., manager ID does not exist)."""
    pass


class RateLimitError(APIError):
    """Raised when too many requests are sent (HTTP 429)."""
    pass


class BaseClient:
    """Reusable HTTP client wrapper with standard headers and retry logic."""
    
    def __init__(self, user_agent: Optional[str] = None, timeout: int = 15, max_retries: int = 3):
        self.timeout = timeout
        self.session = requests.Session()
        
        # Setup headers
        self.session.headers.update({
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        # Setup retry strategy for transient errors (429, 500, 502, 503, 504)
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """
        Performs a GET request and returns the parsed JSON response or raises a typed error.
        """
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)
            response = self.session.get(url, params=params, headers=req_headers, timeout=self.timeout)
            
            if response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Resource at {url} not found (404).", 
                    status_code=404, 
                    response_text=response.text
                )
            elif response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded (429) for {url}.", 
                    status_code=429, 
                    response_text=response.text
                )
            
            response.raise_for_status()
            
            # Check content-type before attempting json decode
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.json()
            return response.text
            
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP Error: {e}", status_code=response.status_code, response_text=response.text) from e
        except requests.exceptions.Timeout as e:
            raise APIError(f"Request timeout after {self.timeout} seconds for {url}") from e
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed for {url}: {e}") from e

    def close(self):
        """Close the underlying session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
