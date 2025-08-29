"""
ComfyUI Video Generation Client for Image-to-Video workflows.

Specialized client for handling video generation tasks with polling,
progress monitoring, and automatic cleanup functionality.
"""

import asyncio
import aiohttp
import json
import uuid
import base64
import io
from typing import Dict, Any, Optional, Callable, List
from urllib.parse import urljoin
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class ComfyUIVideoClient:
    """
    Specialized ComfyUI client for video generation workflows.
    
    Handles the complexities of video generation including longer processing times,
    larger file sizes, and video-specific cleanup operations.
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8188", client_id: str = None):
        """
        Initialize ComfyUI video client.
        
        Args:
            server_url: ComfyUI server base URL with protocol and port
            client_id: Unique client identifier for session tracking
        """
        self.server_url = server_url.rstrip('/')
        self.client_id = client_id or f"video_{uuid.uuid4().hex[:8]}"
        
    async def queue_workflow(self, workflow: Dict[str, Any]) -> str:
        """
        Submit video generation workflow to ComfyUI queue.
        
        Args:
            workflow: Complete ComfyUI workflow dictionary for video generation
        
        Returns:
            str: Unique prompt ID assigned by ComfyUI for tracking
            
        Raises:
            aiohttp.ClientError: When HTTP request fails or server returns error
        """
        queue_url = urljoin(self.server_url, '/prompt')
        print(f"[DEBUG] Sending request to: {queue_url}")
        print(f"[DEBUG] Workflow keys: {list(workflow.keys()) if isinstance(workflow, dict) else 'Not a dict'}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(queue_url, json=workflow, timeout=120.0) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[ERROR] ComfyUI request failed with status {response.status}")
                    print(f"[ERROR] Response: {error_text}")
                    response.raise_for_status()
                result = await response.json()
                return result['prompt_id']
    
    async def upload_image(self, image_base64: str, filename: str = None) -> str:
        """
        Upload base64 image to ComfyUI server and return filename.
        
        Args:
            image_base64: Base64 encoded image data
            filename: Optional filename, generates UUID if not provided
            
        Returns:
            str: Uploaded filename that can be used in LoadImage nodes
            
        Raises:
            aiohttp.ClientError: When upload fails
        """
        if filename is None:
            filename = f"upload_{uuid.uuid4().hex[:8]}.png"
        
        # Decode base64 to image bytes
        try:
            image_data = base64.b64decode(image_base64)
            
            # Verify it's a valid image
            img = Image.open(io.BytesIO(image_data))
            
            # Convert to PNG if needed and get bytes
            if img.format != 'PNG':
                png_buffer = io.BytesIO()
                img.save(png_buffer, format='PNG')
                image_data = png_buffer.getvalue()
                filename = filename.replace('.jpg', '.png').replace('.jpeg', '.png')
                
        except Exception as e:
            raise ValueError(f"Invalid image data: {e}")
        
        upload_url = urljoin(self.server_url, '/upload/image')
        
        # Prepare multipart form data
        data = aiohttp.FormData()
        data.add_field('image', image_data, filename=filename, content_type='image/png')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=data, timeout=30.0) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[ERROR] Image upload failed with status {response.status}")
                    print(f"[ERROR] Response: {error_text}")
                    response.raise_for_status()
                
                result = await response.json()
                return result.get('name', filename)
    
    async def cleanup_files(self) -> bool:
        """
        Clean up both input and output files on ComfyUI server.
        
        Uses POST /files/cleanup endpoint to clean both input and output folders.
        
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        try:
            cleanup_url = urljoin(self.server_url, '/files/cleanup')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(cleanup_url, timeout=30.0) as response:
                    if response.status == 200:
                        result = await response.json()
                        success = result.get('success', False)
                        if success:
                            logger.info("Successfully cleaned up input and output files")
                            return True
                        else:
                            logger.warning(f"Cleanup API returned success=false: {result.get('message', 'Unknown reason')}")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"Cleanup request failed with status {response.status}: {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")
            return False
    
    async def wait_for_video_completion(
        self, 
        prompt_id: str, 
        max_wait: int = 600,  # 10 minutes default for video generation
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Monitor video workflow execution by polling ComfyUI history.
        
        Video generation requires longer timeouts and specialized handling
        for large file transfers and extended processing times.
        
        Args:
            prompt_id: Unique prompt ID from queue_workflow() for tracking
            max_wait: Maximum wait time in seconds (default 10 minutes for video)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict[str, Any]: Final execution result containing:
                - status: Literal["success", "error"] - Execution outcome
                - outputs: Dict - Raw ComfyUI outputs when successful
                - error: Optional[str] - Error message when status="error"
        """
        start_time = asyncio.get_event_loop().time()
        poll_interval = 3.0  # Slower polling for video generation
        
        while (asyncio.get_event_loop().time() - start_time) < max_wait:
            try:
                history_url = urljoin(self.server_url, '/history')
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(history_url, timeout=15.0) as response:
                        if response.status == 200:
                            history_data = await response.json()
                            logger.info(f"Video history check - available prompts: {len(history_data)}")
                            
                            if prompt_id in history_data:
                                prompt_data = history_data[prompt_id]
                                logger.info(f"Found video prompt {prompt_id} in history")
                                
                                status = prompt_data.get('status', {})
                                status_str = status.get('status_str', '')
                                
                                if status_str == 'success' or 'outputs' in prompt_data:
                                    logger.info(f"Video generation completed for {prompt_id}")
                                    return {
                                        'status': 'success',
                                        'outputs': prompt_data.get('outputs', {}),
                                        'prompt_id': prompt_id
                                    }
                                elif status_str == 'error':
                                    error_msg = status.get('messages', ['Unknown video generation error'])
                                    logger.error(f"ComfyUI video generation error: {error_msg}")
                                    return {
                                        'status': 'error',
                                        'error': f"Video generation failed: {error_msg}",
                                        'prompt_id': prompt_id
                                    }
                                else:
                                    logger.info(f"Video still processing {prompt_id}, status: {status_str}")
                                    
                                    if progress_callback:
                                        progress_callback({
                                            'type': 'progress',
                                            'data': {
                                                'prompt_id': prompt_id,
                                                'status': status_str,
                                                'elapsed': asyncio.get_event_loop().time() - start_time
                                            }
                                        })
                            else:
                                logger.info(f"Video prompt {prompt_id} not yet in history")
                                
            except Exception as e:
                logger.warning(f"Error checking video status: {e}")
            
            await asyncio.sleep(poll_interval)
        
        logger.error(f"Timeout waiting for video result: {prompt_id}")
        return {
            'status': 'error',
            'error': f'Video generation timeout after {max_wait}s',
            'prompt_id': prompt_id
        }
    
    async def get_video_base64(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """
        Retrieve generated video as base64 encoded string.
        
        Videos are typically much larger than images and may require
        special handling for download timeouts and memory usage.
        
        Args:
            filename: Generated video filename from ComfyUI output
            subfolder: Optional subdirectory within the folder type
            folder_type: Storage folder type (output, input, temp)
            
        Returns:
            str: Base64 encoded video data
            
        Raises:
            aiohttp.ClientError: When video download fails or file not found
        """
        view_url = urljoin(self.server_url, '/view')
        params = {
            'filename': filename,
            'type': folder_type
        }
        if subfolder:
            params['subfolder'] = subfolder
        
        # Extended timeout for large video files
        async with aiohttp.ClientSession() as session:
            async with session.get(view_url, params=params, timeout=180.0) as response:
                response.raise_for_status()
                video_data = await response.read()
                logger.info(f"Downloaded video: {filename} ({len(video_data)} bytes)")
                return base64.b64encode(video_data).decode('utf-8')
    
    async def get_videos_as_base64_and_cleanup(
        self, 
        prompt_id: str, 
        result_data: Dict[str, Any], 
        cleanup: bool = True
    ) -> List[str]:
        """
        Extract videos from ComfyUI result, convert to base64, and optionally cleanup.
        
        Handles both video and gif formats from various ComfyUI save nodes,
        with automatic server cleanup after successful retrieval.
        
        Args:
            prompt_id: ComfyUI prompt ID for logging purposes
            result_data: Raw ComfyUI completion result containing outputs
            cleanup: Whether to delete videos from server after retrieval
            
        Returns:
            List[str]: List of base64 encoded videos
        """
        base64_videos = []
        files_to_delete = []
        
        try:
            logger.info(f"Processing video result data for {prompt_id}")
            logger.info(f"Video result structure: {json.dumps(result_data, indent=2)}")
            
            outputs = result_data.get('outputs', {})
            logger.info(f"Found {len(outputs)} video output nodes: {list(outputs.keys())}")
            
            if not outputs:
                logger.warning("No outputs found in video result data")
                return base64_videos
            
            # Process each output node for videos
            for node_id, node_output in outputs.items():
                logger.info(f"Processing video node {node_id}: {list(node_output.keys())}")
                
                # Check for various video output formats
                for video_field in ['gifs', 'videos', 'images']:
                    if video_field in node_output:
                        videos = node_output[video_field]
                        logger.info(f"Node {node_id} has {len(videos)} {video_field}")
                        
                        for i, video_info in enumerate(videos):
                            logger.info(f"Processing {video_field[:-1]} {i}: {video_info}")
                            
                            filename = video_info.get('filename')
                            subfolder = video_info.get('subfolder', '')
                            video_type = video_info.get('type', 'output')
                            
                            if not filename:
                                logger.warning(f"No filename in {video_field[:-1]} info: {video_info}")
                                continue
                            
                            # For images field, only process video files
                            if video_field == 'images':
                                video_extensions = ('.mp4', '.avi', '.mov', '.webm', '.gif')
                                if not filename.lower().endswith(video_extensions):
                                    logger.info(f"Skipping non-video file: {filename}")
                                    continue
                            
                            # Get video as base64
                            try:
                                video_base64 = await self.get_video_base64(
                                    filename=filename,
                                    subfolder=subfolder,
                                    folder_type=video_type
                                )
                                base64_videos.append(video_base64)
                                logger.info(f"Successfully retrieved video: {filename} (size: {len(video_base64)} chars)")
                                
                                # Add to cleanup list if needed
                                if cleanup:
                                    files_to_delete.append({
                                        'filename': filename,
                                        'subfolder': subfolder,
                                        'type': video_type
                                    })
                                    
                            except Exception as e:
                                logger.error(f"Failed to get video {filename}: {e}")
            
            # Cleanup files if requested
            if cleanup and files_to_delete:
                logger.info(f"Cleaning up {len(files_to_delete)} video files...")
                for file_info in files_to_delete:
                    try:
                        await self.delete_video(
                            filename=file_info['filename'],
                            subfolder=file_info['subfolder'],
                            video_type=file_info['type']
                        )
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_info['filename']}: {e}")
            
            logger.info(f"Total base64 videos generated: {len(base64_videos)}")
            
        except Exception as e:
            logger.error(f"Error processing videos: {e}", exc_info=True)
        
        return base64_videos
    
    async def delete_video(
        self, 
        filename: str, 
        subfolder: str = '', 
        video_type: str = 'output'
    ) -> bool:
        """
        Delete video file from ComfyUI server storage using /files/single endpoint.
        
        Args:
            filename: Video filename to delete
            subfolder: Optional subdirectory path
            video_type: Storage folder type (output, input, temp)
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            delete_url = urljoin(self.server_url, '/files/single')
            
            payload = {
                'filename': filename,
                'subfolder': subfolder,
                'type': video_type
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    delete_url, 
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=15.0
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        if result.get('success'):
                            logger.info(f"Successfully deleted video: {filename}")
                            return True
                        else:
                            logger.warning(f"Delete API returned success=false for {filename}: {result.get('message')}")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"Video delete request failed with status {response.status}: {error_text}")
                        return False
            
        except Exception as e:
            logger.error(f"Error deleting video {filename}: {e}")
            return False
    
    async def generate_video(
        self, 
        workflow: Dict[str, Any], 
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cleanup: bool = True,
        max_wait: int = 600
    ) -> Dict[str, Any]:
        """
        Execute complete video generation workflow with polling and cleanup.
        
        Orchestrates video generation: workflow submission, polling for completion,
        video retrieval, and optional server cleanup.
        
        Args:
            workflow: Complete ComfyUI video workflow
            progress_callback: Optional callback for progress updates
            cleanup: Whether to delete videos from server after retrieval
            max_wait: Maximum wait time in seconds (default 10 minutes)
            
        Returns:
            Dict[str, Any]: Generation result containing:
                - type: Literal["video_base64", "error"] - Result type
                - video: str - Base64 encoded video when successful
                - videos: List[str] - All videos when multiple generated
                - format: str - Video format (webm, mp4, gif)
                - message: str - Error description when failed
                - prompt_id: str - ComfyUI prompt ID for debugging
        """
        prompt_id = None
        
        try:
            # Queue the video workflow
            prompt_id = await self.queue_workflow(workflow)
            logger.info(f"Queued video workflow with prompt_id: {prompt_id}")
            
            # Wait for completion with video-specific timeout
            execution_result = await self.wait_for_video_completion(
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
            
            # Get all generated videos as base64 with optional cleanup
            base64_videos = await self.get_videos_as_base64_and_cleanup(
                prompt_id=prompt_id,
                result_data=execution_result,
                cleanup=cleanup
            )
            
            if not base64_videos:
                return {
                    'type': 'error',
                    'message': 'No videos generated or failed to retrieve videos',
                    'prompt_id': prompt_id
                }
            
            # Cleanup files if requested
            if cleanup:
                logger.info("Performing post-generation cleanup...")
                try:
                    cleanup_success = await self.cleanup_files()
                    if cleanup_success:
                        logger.info("Post-generation cleanup completed successfully")
                    else:
                        logger.warning("Post-generation cleanup failed, but video was generated successfully")
                except Exception as cleanup_error:
                    logger.error(f"Cleanup error: {cleanup_error}")
                    # Don't fail the whole operation due to cleanup failure
            
            # Determine format from workflow or default to webm
            video_format = "webm"  # Most ComfyUI video workflows output webm
            
            return {
                'type': 'video_base64',
                'video': base64_videos[0],     # First video for backward compatibility
                'videos': base64_videos,       # All videos
                'format': video_format,
                'prompt_id': prompt_id,
                'total_videos': len(base64_videos)
            }
            
        except Exception as e:
            logger.error(f"ComfyUI video generation failed: {e}", exc_info=True)
            return {
                'type': 'error',
                'message': f'Video generation failed: {str(e)}',
                'prompt_id': prompt_id or 'unknown'
            }
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Retrieve ComfyUI system status for video generation monitoring.
        
        Returns:
            Dict[str, Any]: System statistics for queue monitoring
        """
        try:
            async with aiohttp.ClientSession() as session:
                queue_url = urljoin(self.server_url, '/queue')
                async with session.get(queue_url, timeout=10.0) as response:
                    response.raise_for_status()
                    queue_data = await response.json()
                    
                return {
                    'queue_running': len(queue_data.get('queue_running', [])),
                    'queue_pending': len(queue_data.get('queue_pending', []))
                }
        except Exception as e:
            logger.error(f"Failed to get video system stats: {e}")
            return {'error': str(e)}