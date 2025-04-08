import os
import requests
from azure.identity import InteractiveBrowserCredential, ClientSecretCredential, DefaultAzureCredential
import yaml
import logging

# Get logger
logger = logging.getLogger('SecurityCopilotMCP')

class SecurityCopilotClient:
    def __init__(self, credential):
        """
        Initialize the Security Copilot client with Azure authentication.
        
        Args:
            auth_type (str): Authentication type - "interactive", "client_secret", or "default"
        """
        self.credential = credential
        self.base_url = os.getenv('SECURITY_COPILOT_API_URL', 'https://api.securitycopilot.microsoft.com')
        self.region = os.getenv('SECURITY_COPILOT_REGION', 'eastus')
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info(f"SecurityCopilotClient initialized with base_url={self.base_url}, region={self.region}")
    
    def _get_authenticated_headers(self, content_type="application/json"):
        """
        Get headers with authentication token.
        
        Args:
            content_type (str): Content type for the headers
            
        Returns:
            dict: Headers with authentication token
        """
        if not self.credential:
            logger.error("Authentication required but no credential provided")
            raise Exception("Authentication required")
        
        try:
            logger.debug("Getting authentication token")
            self.token = self.credential.get_token("https://api.securitycopilot.microsoft.com/.default")
            headers = {
                "Content-Type": content_type,
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token.token}"
            }
            logger.debug("Authentication token obtained successfully")
            return headers
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise Exception(f"Failed to refresh token: {str(e)}")
    
    def get_skillsets(self, filter_name=None,full_response=True):
        """
        Get all skillsets with their related skills from Security Copilot.
        
        Args:
            filter_name (str, optional): Filter skillsets by name (contains filter)
            full_response (bool, optional): Whether to return the full response from Security Copilot   
        Returns:
            dict: All skillsets with their related skills
        """
        # Get authenticated headers
        headers = self._get_authenticated_headers()
            
        # Get all skillsets
        skillsets_url = f"{self.base_url}/geo/{self.region}/skillsets"
        response = requests.get(skillsets_url, headers=headers)
        response.raise_for_status()
        
        skillsets_data = response.json()
        filtered_skillsets = []
        for skillset in skillsets_data.get('value', []):
            if filter_name and filter_name.lower() not in skillset['name'].lower():
                continue
            filtered_skillsets.append(skillset)
        
        if full_response:   
            # For each skillset, get its skills
            skillsets_with_skills = []
            for skillset in filtered_skillsets:
                # Apply filter if provided
                
                    
                # Get skills for this skillset
                skills_url = f"{self.base_url}/geo/{self.region}/skillsets/{skillset['name']}/skills"
                skills_response = requests.get(skills_url, headers=headers)
                
                if skills_response.status_code == 200:
                    skills_data = skills_response.json()
                    # Add skills to skillset
                    skillset['skills'] = skills_data.get('value', [])
                else:
                    # If skills can't be retrieved, add empty list
                    skillset['skills'] = []
                    
                skillsets_with_skills.append(skillset)
            
            return {
                "count": len(skillsets_with_skills),
                "skillsets": skillsets_with_skills
            }
        else:
            return {
                "count": len(skillsets_data.get('value', [])),
                "skillsets": skillsets_data.get('value', [])
            }
        
    def upload_skillset(self, yaml_content, create_if_not_exists=True):
        """
        Upload or update a skillset in Security Copilot.
        
        Args:
            yaml_content (str): The YAML content of the skillset to upload
            create_if_not_exists (bool): Whether to create the skillset if it doesn't exist
            
        Returns:
            dict: The response from Security Copilot
        """
        # Parse YAML to extract plugin name
        import yaml
        try:
            plugin_object = yaml.safe_load(yaml_content)
            plugin_name = plugin_object['Descriptor']['Name']
        except Exception as e:
            raise Exception(f"Failed to parse YAML content: {str(e)}")
        
        if not plugin_name:
            raise Exception("Plugin name not found in YAML content")
        
        # Get authenticated headers
        headers = self._get_authenticated_headers()
        
        # Check if plugin exists
        skillsets_url = f"{self.base_url}/geo/{self.region}/skillsets"
        response = requests.get(skillsets_url, headers=headers)
        response.raise_for_status()
        
        existing_plugins = response.json().get('value', [])
        plugin_exists = any(plugin['name'] == plugin_name for plugin in existing_plugins)
        
        query_params = "?scope=Tenant&skillsetFormat=SkillsetYaml"
        
        # Set the proper content type for YAML
        yaml_headers = self._get_authenticated_headers("application/yaml")
        
        if plugin_exists:
            # Update existing plugin
            update_url = f"{skillsets_url}/{plugin_name}{query_params}"
            response = requests.put(update_url, data=yaml_content, headers=yaml_headers)
            response.raise_for_status()
            return {"status": "updated", "name": plugin_name, "response": response.json()}
        elif create_if_not_exists:
            # Create new plugin
            create_url = f"{skillsets_url}{query_params}"
            response = requests.post(create_url, data=yaml_content, headers=yaml_headers)
            response.raise_for_status()
            return {"status": "created", "name": plugin_name, "response": response.json()}
        else:
            return {"status": "not_found", "name": plugin_name} 
    
    def create_new_session(self, session_name="New Security Copilot session"):
        """
        Create a new session in Security Copilot.
        
        Args:
            session_name (str): The name of the session to create
            
        Returns:
            dict: The response from Security Copilot
        """
        # Get authenticated headers
        headers = self._get_authenticated_headers()
        
        # Create session payload
        payload = {
            "name": session_name
        }
        
        # Create new session
        sessions_url = f"{self.base_url}/sessions"
        response = requests.post(sessions_url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.json() 
     
    def create_prompt(self, session_id, prompt_type="Prompt", content=None, skill_name=None, inputs=None):
        """
        Create a prompt in a Security Copilot session.
        
        Args:
            session_id (str): The ID of the session
            prompt_type (str): The type of prompt - "Prompt" or "Skill"
            content (str, optional): The content of the prompt (required if prompt_type is "Prompt")
            skill_name (str, optional): The name of the skill (required if prompt_type is "Skill")
            inputs (dict, optional): The inputs for the skill (required if prompt_type is "Skill")
            
        Returns:
            dict: The response from Security Copilot containing the promptId
        """
        logger.info(f"Creating prompt with type: {prompt_type}")
        logger.debug(f"Session ID: {session_id}")
        
        # Get authenticated headers
        headers = self._get_authenticated_headers()
        
        # Validate parameters
        if prompt_type not in ["Prompt", "Skill"]:
            logger.error(f"Invalid prompt_type: {prompt_type}")
            raise ValueError("prompt_type must be either 'Prompt' or 'Skill'")
        
        if prompt_type == "Prompt" and not content:
            logger.error("Content is required for prompt_type 'Prompt' but not provided")
            raise ValueError("content is required for prompt_type 'Prompt'")
        
        if prompt_type == "Skill" and not skill_name:
            logger.error("skill_name is required for prompt_type 'Skill' but not provided")
            raise ValueError("skill_name is required for prompt_type 'Skill'")
        
        # Create payload
        payload = {
            "PromptType": prompt_type
        }
        
        if prompt_type == "Prompt":
            payload["Content"] = content
            logger.debug(f"Prompt content length: {len(content) if content else 0}")
        else:  # Skill
            payload["SkillName"] = skill_name
            payload["Inputs"] = inputs or {}
            logger.debug(f"Using Skill: {skill_name}")
            logger.debug(f"Skill inputs: {inputs}")
        
        logger.debug(f"Request payload: {payload}")
        
        # Create prompt
        prompts_url = f"{self.base_url}/sessions/{session_id}/prompts"
        logger.debug(f"POST request to: {prompts_url}")
        
        try:
            response = requests.post(prompts_url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(f"Error creating prompt: {response.status_code} - {response.text}")
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Prompt created successfully with ID: {response_data.get('promptId')}")
            #logger.debug(f"Full response: {response_data}")
            return response_data
        except Exception as e:
            logger.error(f"Failed to create prompt: {str(e)}")
            raise
        
        return response.json() 

    def create_evaluation(self, session_id, prompt_id):
        """
        Create an evaluation for a prompt in a Security Copilot session.
        
        Args:
            session_id (str): The ID of the session
            prompt_id (str): The ID of the prompt to evaluate
            
        Returns:
            dict: The response from Security Copilot containing the evaluationId
        """
        logger.info(f"Creating evaluation for prompt_id: {prompt_id}")
        
        # Get authenticated headers
        headers = self._get_authenticated_headers()
        
        # Create evaluation with empty payload
        payload = {}
        
        # Create evaluation
        evaluations_url = f"{self.base_url}/sessions/{session_id}/prompts/{prompt_id}/evaluations"
        logger.debug(f"POST request to: {evaluations_url}")
        
        try:
            response = requests.post(evaluations_url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.error(f"Error creating evaluation: {response.status_code} - {response.text}")
            response.raise_for_status()
            response_data = response.json()
            evaluation_id = response_data.get("evaluation", {}).get("evaluationId")
            logger.info(f"Evaluation created successfully with ID: {evaluation_id}")
            #logger.debug(f"Full response: {response_data}")
            return response_data
        except Exception as e:
            logger.error(f"Failed to create evaluation: {str(e)}")
            raise

    def poll_evaluation(self, session_id, prompt_id, evaluation_id, polling_interval=2, max_attempts=30):
        """
        Poll the evaluation results until completion.
        
        Args:
            session_id (str): The ID of the session
            prompt_id (str): The ID of the prompt
            evaluation_id (str): The ID of the evaluation
            polling_interval (int): Time in seconds between polling attempts
            max_attempts (int): Maximum number of polling attempts
            
        Returns:
            dict: The completed evaluation result or the last polled state
        """
        logger.info(f"Polling evaluation ID: {evaluation_id}")
        logger.debug(f"Polling interval: {polling_interval}s, max attempts: {max_attempts}")
        
        # Get authenticated headers
        headers = self._get_authenticated_headers()
        
        # Polling endpoint
        evaluation_url = f"{self.base_url}/sessions/{session_id}/prompts/{prompt_id}/evaluations/{evaluation_id}"
        
        import time
        
        # Poll for results
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            logger.debug(f"Polling attempt {attempts}/{max_attempts}")
            
            try:
                response = requests.get(evaluation_url, headers=headers)
                if response.status_code >= 400:
                    logger.error(f"Error polling evaluation: {response.status_code} - {response.text}")
                response.raise_for_status()
                
                evaluation_data = response.json()
                state = evaluation_data.get("state")
                logger.debug(f"Current evaluation state: {state}")
                # Check if evaluation is completed
                if state == "Completed":
                    logger.info(f"Evaluation completed after {attempts} polling attempts")
                    return evaluation_data
                
                # Wait before next poll
                time.sleep(polling_interval)
            except Exception as e:
                logger.error(f"Error during polling: {str(e)}")
                # Continue polling despite errors
        
        logger.warning(f"Max polling attempts ({max_attempts}) reached without completion")
        # Return the last state if max attempts reached
        return evaluation_data 
        
    def process_prompt(self, prompt_type="Prompt", content=None, skill_name=None, inputs=None, 
                       session_name="Security Copilot Session", polling_interval=2, max_attempts=30):
        """
        Complete workflow to process a prompt and get results.
        
        This method:
        1. Creates a new session
        2. Creates a prompt in that session
        3. Creates an evaluation for that prompt
        4. Polls until the evaluation is complete
        5. Returns the final result
        
        Args:
            prompt_type (str): The type of prompt - "Prompt" or "Skill"
            content (str, optional): The content of the prompt (required if prompt_type is "Prompt")
            skill_name (str, optional): The name of the skill (required if prompt_type is "Skill")
            inputs (dict, optional): The inputs for the skill (required if prompt_type is "Skill")
            session_name (str): The name for the new session
            polling_interval (int): Time in seconds between polling attempts
            max_attempts (int): Maximum number of polling attempts
            
        Returns:
            dict: The completed evaluation result
        """
        logger.info(f"Processing {prompt_type} with session name: {session_name}")
        if prompt_type == "Skill":
            logger.info(f"Skill name: {skill_name}")
            logger.debug(f"Skill inputs: {inputs}")
        
        try:
            # 1. Create a new session
            logger.debug("Step 1: Creating a new session")
            session_response = self.create_new_session(session_name)
            session_id = session_response.get("sessionId")
            
            if not session_id:
                logger.error("Failed to create session. No sessionId in response.")
                logger.debug(f"Session response: {session_response}")
                raise Exception("Failed to create session. No sessionId in response.")
            
            logger.debug(f"Session created with ID: {session_id}")
            
            # 2. Create a prompt in the session
            logger.debug("Step 2: Creating a prompt in the session")
            prompt_response = self.create_prompt(
                session_id=session_id,
                prompt_type=prompt_type,
                content=content,
                skill_name=skill_name,
                inputs=inputs
            )
            
            prompt_id = prompt_response.get("promptId")
            if not prompt_id:
                logger.error("Failed to create prompt. No promptId in response.")
                logger.debug(f"Prompt response: {prompt_response}")
                raise Exception("Failed to create prompt. No promptId in response.")
            
            logger.debug(f"Prompt created with ID: {prompt_id}")
            
            # 3. Create an evaluation for the prompt
            logger.debug("Step 3: Creating an evaluation for the prompt")
            evaluation_response = self.create_evaluation(session_id, prompt_id)
            evaluation_id = evaluation_response.get("evaluation", {}).get("evaluationId")
            
            if not evaluation_id:
                logger.error("Failed to create evaluation. No evaluationId in response.")
                logger.debug(f"Evaluation response: {evaluation_response}")
                raise Exception("Failed to create evaluation. No evaluationId in response.")
            
            logger.debug(f"Evaluation created with ID: {evaluation_id}")
            
            # 4. Poll until the evaluation is complete
            logger.debug("Step 4: Polling until the evaluation is complete")
            result = self.poll_evaluation(
                session_id=session_id,
                prompt_id=prompt_id,
                evaluation_id=evaluation_id,
                polling_interval=polling_interval,
                max_attempts=max_attempts
            )
            
            logger.info("Prompt processing completed successfully")
            
            # 5. Return the final result
            return {
                "session_id": session_id,
                "prompt_id": prompt_id,
                "evaluation_id": evaluation_id,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error during prompt processing: {str(e)}", exc_info=True)
            raise 