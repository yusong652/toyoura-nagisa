"""
ComfyUI API client for image generation.

Provides a comprehensive client for interacting with ComfyUI's WebSocket and HTTP APIs,
supporting workflow execution, progress monitoring, and result retrieval.
"""

import asyncio
import aiohttp
import json
import uuid
import base64
from typing import Dict, Any, Optional, Callable, List
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """
    Asynchronous ComfyUI API client for image generation workflows.
    
    Manages WebSocket connections for real-time progress monitoring and HTTP requests
    for workflow submission and result retrieval.
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8188", client_id: str = None):
        """
        Initialize ComfyUI client with server configuration.
        
        Args:
            server_url: ComfyUI server base URL with protocol and port
            client_id: Unique client identifier for WebSocket session tracking
        """
        self.server_url = server_url.rstrip('/')
        self.client_id = client_id or str(uuid.uuid4())
        self.ws_url = self.server_url.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws'
        
    async def queue_prompt(self, workflow: Dict[str, Any]) -> str:
        """
        Submit workflow to ComfyUI queue for processing.
        
        Sends workflow prompt to ComfyUI's queue endpoint and returns the assigned prompt ID
        for tracking execution progress and retrieving results.
        
        Args:
            workflow: Complete ComfyUI workflow dictionary with nodes and connections
        
        Returns:
            str: Unique prompt ID assigned by ComfyUI for workflow tracking
            
        Raises:
            aiohttp.ClientError: When HTTP request fails or server returns error
        """
        queue_url = urljoin(self.server_url, '/prompt')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(queue_url, json=workflow) as response:
                response.raise_for_status()
                result = await response.json()
                return result['prompt_id']
    
    async def get_image_base64(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """
        Retrieve generated image as base64 encoded string.
        
        Downloads image file from ComfyUI server storage and converts to base64 format
        for transmission and embedding in responses.
        
        Args:
            filename: Generated image filename from ComfyUI output
            subfolder: Optional subdirectory within the folder type
            folder_type: Storage folder type (output, input, temp)
            
        Returns:
            str: Base64 encoded image data without data URI prefix
            
        Raises:
            aiohttp.ClientError: When image download fails or file not found
        """
        view_url = urljoin(self.server_url, '/view')
        params = {
            'filename': filename,
            'type': folder_type
        }
        if subfolder:
            params['subfolder'] = subfolder
        
        async with aiohttp.ClientSession() as session:
            async with session.get(view_url, params=params, timeout=30.0) as response:
                response.raise_for_status()
                image_data = await response.read()
                return base64.b64encode(image_data).decode('utf-8')
    
    async def get_images_as_base64_and_cleanup(
        self, 
        prompt_id: str, 
        result_data: Dict[str, Any], 
        cleanup: bool = True
    ) -> List[str]:
        """
        Extract images from ComfyUI result, convert to base64, and optionally cleanup.
        
        Processes ComfyUI output data to extract all generated images, convert them
        to base64 format, and optionally delete them from the server storage.
        
        Args:
            prompt_id: ComfyUI prompt ID for logging purposes
            result_data: Raw ComfyUI completion result containing outputs
            cleanup: Whether to delete images from server after retrieval
            
        Returns:
            List[str]: List of base64 encoded images
            
        Note:
            Cleanup functionality depends on server configuration and may require
            appropriate permissions to delete files from ComfyUI output directory.
        """
        base64_images = []
        files_to_delete = []
        
        try:
            logger.info(f"Processing result data for {prompt_id}")
            logger.info(f"Result data structure: {json.dumps(result_data, indent=2)}")
            
            # Extract outputs from result data
            outputs = result_data.get('outputs', {})
            logger.info(f"Found {len(outputs)} output nodes: {list(outputs.keys())}")
            
            if not outputs:
                logger.warning("No outputs found in result data")
                return base64_images
            
            # Process each output node
            for node_id, node_output in outputs.items():
                logger.info(f"Processing node {node_id}: {list(node_output.keys())}")
                
                if 'images' in node_output:
                    images = node_output['images']
                    logger.info(f"Node {node_id} has {len(images)} images")
                    
                    for i, image_info in enumerate(images):
                        logger.info(f"Processing image {i}: {image_info}")
                        
                        filename = image_info.get('filename')
                        subfolder = image_info.get('subfolder', '')
                        image_type = image_info.get('type', 'output')
                        
                        if not filename:
                            logger.warning(f"No filename in image info: {image_info}")
                            continue
                        
                        # Get image as base64
                        try:
                            image_base64 = await self.get_image_base64(
                                filename=filename,
                                subfolder=subfolder,
                                folder_type=image_type
                            )
                            base64_images.append(image_base64)
                            logger.info(f"Successfully retrieved image: {filename} (size: {len(image_base64)} chars)")
                            
                            # Add to cleanup list if needed
                            if cleanup:
                                files_to_delete.append({
                                    'filename': filename,
                                    'subfolder': subfolder,
                                    'type': image_type
                                })
                                
                        except Exception as e:
                            logger.error(f"Failed to get image {filename}: {e}")
                else:
                    logger.info(f"Node {node_id} has no images key")
            
            # Cleanup files if requested
            if cleanup and files_to_delete:
                logger.info(f"Cleaning up {len(files_to_delete)} image files...")
                for file_info in files_to_delete:
                    try:
                        await self.delete_image(
                            filename=file_info['filename'],
                            subfolder=file_info['subfolder'],
                            image_type=file_info['type']
                        )
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_info['filename']}: {e}")
            
            logger.info(f"Total base64 images generated: {len(base64_images)}")
            
        except Exception as e:
            logger.error(f"Error processing images: {e}", exc_info=True)
        
        return base64_images
    
    async def delete_image(
        self, 
        filename: str, 
        subfolder: str = '', 
        image_type: str = 'output'
    ) -> bool:
        """
        Delete image file from ComfyUI server storage using custom delete API.
        
        Uses the /files/single endpoint to delete specific image files from
        the ComfyUI server storage directory.
        
        Args:
            filename: Image filename to delete
            subfolder: Optional subdirectory path
            image_type: Storage folder type (output, input, temp)
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            delete_url = urljoin(self.server_url, '/files/single')
            
            payload = {
                'filename': filename,
                'subfolder': subfolder,
                'type': image_type
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    delete_url, 
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10.0
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            logger.info(f"Successfully deleted image: {filename}")
                            return True
                        else:
                            logger.warning(f"Delete API returned success=false for {filename}: {result.get('message', 'Unknown reason')}")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"Delete request failed with status {response.status}: {error_text}")
                        return False
            
        except Exception as e:
            logger.error(f"Error deleting image {filename}: {e}")
            return False
    
    async def wait_for_completion(
        self, 
        prompt_id: str, 
        max_wait: int = 120,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Monitor workflow execution by polling ComfyUI history endpoint.
        
        Uses polling approach instead of WebSocket to check completion status,
        which is more reliable for remote ComfyUI servers.
        
        Args:
            prompt_id: Unique prompt ID from queue_prompt() for tracking
            max_wait: Maximum wait time in seconds
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict[str, Any]: Final execution result containing:
                - status: Literal["success", "error"] - Execution outcome
                - outputs: Dict - Raw ComfyUI outputs when successful
                - error: Optional[str] - Error message when status="error"
                
        Raises:
            asyncio.TimeoutError: When execution exceeds max_wait time
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < max_wait:
            try:
                # Check history for completion
                history_url = urljoin(self.server_url, '/history')
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(history_url, timeout=10.0) as response:
                        if response.status == 200:
                            history_data = await response.json()
                            logger.info(f"History data keys: {list(history_data.keys()) if history_data else 'None'}")
                            
                            # Check if our prompt_id is in history
                            if prompt_id in history_data:
                                prompt_data = history_data[prompt_id]
                                logger.info(f"Found prompt {prompt_id} in history, status: {prompt_data.get('status', {})}")
                                
                                # Check completion status
                                status = prompt_data.get('status', {})
                                status_str = status.get('status_str', '')
                                
                                if status_str == 'success' or 'outputs' in prompt_data:
                                    logger.info(f"Generation completed for {prompt_id}")
                                    return {
                                        'status': 'success',
                                        'outputs': prompt_data.get('outputs', {}),
                                        'prompt_id': prompt_id
                                    }
                                elif status_str == 'error':
                                    logger.error(f"ComfyUI generation error: {prompt_data}")
                                    return {
                                        'status': 'error',
                                        'error': f"ComfyUI generation failed: {status.get('messages', 'Unknown error')}",
                                        'prompt_id': prompt_id
                                    }
                                else:
                                    logger.info(f"Still processing {prompt_id}, status: {status}")
                                    
                                    # Call progress callback if available
                                    if progress_callback:
                                        progress_callback({
                                            'type': 'progress',
                                            'data': {
                                                'prompt_id': prompt_id,
                                                'status': status_str
                                            }
                                        })
                            else:
                                logger.info(f"Prompt {prompt_id} not yet in history")
                                
            except Exception as e:
                logger.warning(f"Error checking ComfyUI status: {e}")
            
            # Wait before next check
            await asyncio.sleep(1.0)
        
        logger.error(f"Timeout waiting for ComfyUI result: {prompt_id}")
        return {
            'status': 'error',
            'error': f'Workflow execution timeout after {max_wait}s',
            'prompt_id': prompt_id
        }
    
    async def generate_image(
        self, 
        workflow: Dict[str, Any], 
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cleanup: bool = True,
        max_wait: int = 120
    ) -> Dict[str, Any]:
        """
        Execute complete image generation workflow with polling and cleanup.
        
        Orchestrates the full ComfyUI workflow execution cycle: queue submission,
        progress monitoring via polling, base64 image retrieval, and optional cleanup.
        
        Args:
            workflow: Complete ComfyUI workflow with prompt, client_id, and settings
            progress_callback: Optional callback for real-time progress updates
            cleanup: Whether to delete images from server after retrieval
            max_wait: Maximum wait time in seconds for completion
            
        Returns:
            Dict[str, Any]: Generation result containing:
                - type: Literal["image_base64", "error"] - Result type indicator
                - image: str - Base64 encoded image when type="image_base64"
                - images: List[str] - All base64 images when multiple generated
                - message: str - Error description when type="error"
                - prompt_id: str - ComfyUI prompt ID for debugging
                
        Example:
            workflow = comfyui_config.generate_workflow(
                positive_prompt="anime girl, masterpiece",
                negative_prompt="low quality, blurry"
            )
            result = await client.generate_image(workflow)
            if result["type"] == "image_base64":
                image_data = result["image"]
        """
        prompt_id = None
        
        try:
            # Queue the workflow
            prompt_id = await self.queue_prompt(workflow)
            logger.info(f"Queued workflow with prompt_id: {prompt_id}")
            
            # Wait for completion using polling
            execution_result = await self.wait_for_completion(
                prompt_id, 
                max_wait=max_wait, 
                progress_callback=progress_callback
            )
            
            if execution_result['status'] == 'error':
                return {
                    'type': 'error',
                    'message': execution_result['error'],
                    'prompt_id': prompt_id
                }
            
            # Get all generated images as base64 with optional cleanup
            base64_images = await self.get_images_as_base64_and_cleanup(
                prompt_id=prompt_id,
                result_data=execution_result,
                cleanup=cleanup
            )
            
            if not base64_images:
                return {
                    'type': 'error',
                    'message': 'No images generated or failed to retrieve images',
                    'prompt_id': prompt_id
                }
            
            return {
                'type': 'image_base64',
                'image': base64_images[0],  # First image for backward compatibility
                'images': base64_images,    # All images
                'prompt_id': prompt_id,
                'total_images': len(base64_images)
            }
            
        except Exception as e:
            logger.error(f"ComfyUI generation failed: {e}", exc_info=True)
            return {
                'type': 'error',
                'message': f'Image generation failed: {str(e)}',
                'prompt_id': prompt_id or 'unknown'
            }
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Retrieve ComfyUI system status and queue information.
        
        Fetches current system statistics including queue length, processing status,
        and available resources for monitoring server health.
        
        Returns:
            Dict[str, Any]: System statistics with structure:
                - queue_running: int - Currently executing workflows
                - queue_pending: int - Workflows waiting in queue
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get queue status
                queue_url = urljoin(self.server_url, '/queue')
                async with session.get(queue_url) as response:
                    response.raise_for_status()
                    queue_data = await response.json()
                    
                return {
                    'queue_running': len(queue_data.get('queue_running', [])),
                    'queue_pending': len(queue_data.get('queue_pending', []))
                }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {'error': str(e)}