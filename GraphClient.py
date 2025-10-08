import requests
import logging

logger = logging.getLogger('SecurityCopilotMCP')

class GraphClient:
    """Client for interacting with Microsoft Graph API"""
    
    base_url = "https://graph.microsoft.com/v1.0"
    scope = "https://graph.microsoft.com/.default"
    
    def __init__(self, credential):
        """
        Initialize the Graph client with Azure authentication.
        
        Args:
            credential: Azure credential object for authentication
        """
        self.credential = credential
        logger.info("GraphClient initialized")
    
    def _get_authenticated_headers(self):
        """Get authenticated headers for Graph API requests"""
        try:
            token = self.credential.get_token(self.scope)
            return {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            logger.error(f"Failed to get authentication token: {str(e)}")
            raise
    
    def get_secure_score_controls(self):
        """
        Retrieve the list of Microsoft Secure Score control profiles.
        
        Returns:
            dict: Response containing secure score control profiles
        """
        logger.info("Retrieving Microsoft Secure Score control profiles")
        
        try:
            headers = self._get_authenticated_headers()
            url = f"{self.base_url}/security/secureScoreControlProfiles"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            controls = data.get('value', [])
            
            logger.info(f"Successfully retrieved {len(controls)} secure score control profiles")
            
            return {
                "status": "success",
                "count": len(controls),
                "controls": controls
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            return {
                "status": "error",
                "error": f"HTTP error: {str(e)}",
                "details": e.response.text if hasattr(e, 'response') else None
            }
        except Exception as e:
            logger.error(f"Error retrieving secure score controls: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
