import asyncio
import os
import argparse
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from azure.identity import InteractiveBrowserCredential, ClientSecretCredential, DefaultAzureCredential  
from SecurityCopilotClient import SecurityCopilotClient
from SentinelClient import SentinelClient 
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SecurityCopilotMCP')
logger.info("Starting Security Copilot MCP Server")
# Load environment variables
load_dotenv()

mcp = FastMCP('MicrosoftSecurityCopilot-server')

securitycopilot_client = None
sentinel_client = None

@mcp.tool()
def run_sentinel_query(query: str) -> str:
    """ Run a query against Sentinel.
    Args:
        query: The Kusto Query Language (KQL) query to run
    Returns:
        Results from the query
    """
    global sentinel_client
    return sentinel_client.run_query(query)
@mcp.tool()
def upload_plugin(plugin_yaml_content: str, create_if_not_exists: bool = True) -> str:
    """
    Upload or update a skillset in Security Copilot.
    
    Args:
        plugin_yaml_content: Raw YAML content of the plugin definition. Include the full file content
        create_if_not_exists: Whether to create the skillset if it doesn't exist
    
    Returns:
        Response from Security Copilot
    """
    global securitycopilot_client
    
    try:
        results = securitycopilot_client.upload_skillset(plugin_yaml_content, create_if_not_exists)
        return results
    except Exception as e:
        return f"Error uploading skillset: {str(e)}"
@mcp.tool()
def get_skillsets(filter_name: str=None,full_response: bool = True) -> str:
    """Get skillsets from Security Copilot.
    Args:
        filter_name: Filter name to get skillsets from Security Copilot
        full_response: Whether to return the full response including skills from Security Copilot
    Returns:
        Skillsets from Security Copilot
    """
    print("[+] Getting skillsets from Security Copilot with filter name: ",filter_name if filter_name else "None"  )
    try:    
        global securitycopilot_client
        return securitycopilot_client.get_skillsets(filter_name,full_response)    
    except Exception as e:
        return f"Error getting skillsets: {str(e)}"

@mcp.tool()
def run_prompt(prompt_type: str = "Prompt", content: str = None, skill_name: str = None, 
               inputs: dict = None, session_name: str = "Security Copilot Session", 
               polling_interval: int = 2, max_attempts: int = 30) -> str:
    """
    Run a prompt in Security Copilot and get the results.
    
    Args:
        prompt_type: The type of prompt - "Prompt" or "Skill"
        content: The content of the prompt (required if prompt_type is "Prompt")
        skill_name: The name of the skill (required if prompt_type is "Skill")
        inputs: The inputs for the skill (required if prompt_type is "Skill")
        session_name: The name for the new session
        polling_interval: Time in seconds between polling attempts
        max_attempts: Maximum number of polling attempts
    
    Returns:
        Results from Security Copilot
    """
    global securitycopilot_client
    
    try:
        results = securitycopilot_client.process_prompt(
            prompt_type=prompt_type,
            content=content,
            skill_name=skill_name,
            inputs=inputs,
            session_name=session_name,
            polling_interval=polling_interval,
            max_attempts=max_attempts
        )
        return results
    except Exception as e:
        return f"Error processing prompt: {str(e)}"

def run_tests():
    """Run test queries to verify functionality."""
    print("[+] Running Sentinel Test")
    sentinel_result = run_sentinel_query("Usage |project DataType | take 10")
    if sentinel_result["status"] == "success":
        print("[+] Sentinel Test executed successfully")
    else:
        print("[+] Sentinel Test failed")
    print("[+] Running Security Copilot Prompt Test")   
    prompt_result = run_prompt(prompt_type="Prompt", content="What is the most common alert type in defender for the last 24 hours?")
    if "session_id" in prompt_result and "prompt_id" in prompt_result and "evaluation_id" in prompt_result:
        print("[+] Security Copilot Prompt Test executed successfully")
    else:
        print("[+] Security Copilot Prompt Test failed")
    # Run Security copilot Skill prompt test
    print("[+] Running Security Copilot Skill Test")
    skill_result = run_prompt(prompt_type="Skill", skill_name="GetAbnormalSignIns", inputs={"UniquePropertiesThreshold": "3", "Period": "24h", "Limit": "10"})
    if "session_id" in skill_result and "prompt_id" in skill_result and "evaluation_id" in skill_result:
        print("[+] Security Copilot Skill Test executed successfully")
    else:
        print("[+] Security Copilot Skill Test failed")
    print("[+] Running Security Copilot Skillsets Test")
    skillsets = get_skillsets("Entra",full_response=False)
    if skillsets["count"] > 0:
        print("[+] Security Copilot Skillsets Test executed successfully")
    else:
        print("[+] Security Copilot Skillsets Test failed")
def auth(auth_type):  
    """  
    Authenticate with Azure using different credential types based on the provided auth_type.  
    """  
    if auth_type == "interactive":
        credential = InteractiveBrowserCredential()
    elif auth_type == "client_secret":
        credential = ClientSecretCredential(
            tenant_id=os.getenv('AZURE_TENANT_ID'),
            client_id=os.getenv('AZURE_CLIENT_ID'),
            client_secret=os.getenv('AZURE_CLIENT_SECRET')
        )
    else:
        # Default credential for managed identities
        credential = DefaultAzureCredential()
    # Force authentication to make the user login  
    try:  
        credential.get_token("https://api.securitycopilot.microsoft.com/.default")  
    except Exception as e:  
        print(f"Authentication failed: {e}")  
        print("Only unauthenticated tools can be used")  
    return credential      

def create_clients(auth_credential):  
    """  
    Create clients to external platforms using environment variables.  
    """  
    global securitycopilot_client, sentinel_client
    
    if securitycopilot_client is None:
        securitycopilot_client = SecurityCopilotClient(auth_credential)
    
    if sentinel_client is None:
        subscriptionId=os.getenv('SENTINEL_SUBSCRIPTION_ID')
        resourceGroupName=os.getenv('SENTINEL_RESOURCE_GROUP')
        workspaceName=os.getenv('SENTINEL_WORKSPACE_NAME')
        workspace_id=os.getenv('SENTINEL_WORKSPACE_ID')
        sentinel_client = SentinelClient(auth_credential,subscriptionId,resourceGroupName,workspaceName,workspace_id)
    return securitycopilot_client, sentinel_client

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Security Copilot MCP Server")
    parser.add_argument("--run-tests", action="store_true", help="Run tests before starting the server")
    args = parser.parse_args()
    
    #Create clients
    print("[+] Authenticating using ", os.getenv('AUTHENTICATION_TYPE', 'interactive'))
    auth_credential = auth(os.getenv('AUTHENTICATION_TYPE', 'interactive'))
    create_clients(auth_credential)
    
    # Run tools test only if specified
    if args.run_tests:
        print("[+] Running tests...")
        run_tests()
    
    # Run MCP server with SSE transport
    print("[+] Starting MCP server...")
    mcp.run(transport="sse")





