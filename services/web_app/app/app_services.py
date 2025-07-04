import os
import json
import asyncio
from PIL import Image
from markdown import markdown
import io
import base64
import traceback
import uuid
import zipfile
import shutil
import queue
import threading
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Response, stream_with_context, jsonify, current_app, send_from_directory, url_for, send_file, after_this_request
from . import app, cleanup_file

try:
    from vlm4ocr.ocr_engines import OCREngine
    from vlm4ocr.vlm_engines import OpenAIVLMEngine, AzureOpenAIVLMEngine, OllamaVLMEngine, BasicVLMConfig
except ImportError as e:
    print(f"Error importing from vlm4ocr in app_services.py: {e}")
    raise

# A temporary directory to store batch results.
TEMP_DIR = Path(app.app_config.get("temp_directory", "temp"))
TEMP_DIR.mkdir(exist_ok=True)


def _initialize_ocr_engine(form_data):
    """
    Helper function to initialize the OCREngine based on form data.
    This consolidates the engine setup logic for both single and batch processing.
    """
    vlm_api = form_data.get('vlm_api', '')
    user_prompt = form_data.get('user_prompt', None)
    output_format = form_data.get('output_format', 'markdown')
    try:
        max_new_tokens = int(form_data.get('max_new_tokens', '4096'))
        temperature = float(form_data.get('temperature', '0.0'))
    except (ValueError, TypeError):
        raise ValueError("Invalid value for Max New Tokens or Temperature.")

    print(f"Initializing VLM Engine for API: {vlm_api}")
    config = BasicVLMConfig(max_new_tokens=max_new_tokens, temperature=temperature)

    vlm_engine = None
    if vlm_api == "openai_compatible":
        vlm_engine = OpenAIVLMEngine(
            model=form_data.get('vlm_model'),
            api_key=form_data.get('openai_compatible_api_key'),
            base_url=form_data.get('vlm_base_url'),
            config=config
        )
    elif vlm_api == "openai":
        vlm_engine = OpenAIVLMEngine(
            model=form_data.get('openai_model'),
            api_key=form_data.get('openai_api_key'),
            config=config
        )
    elif vlm_api == "azure_openai":
        vlm_engine = AzureOpenAIVLMEngine(
            model=form_data.get('azure_deployment_name'),
            api_key=form_data.get('azure_openai_api_key'),
            azure_endpoint=form_data.get('azure_endpoint'),
            api_version=form_data.get('azure_api_version'),
            config=config
        )
    elif vlm_api == "ollama":
        vlm_engine = OllamaVLMEngine(
            model_name=form_data.get('ollama_model'),
            host=form_data.get('ollama_host', 'http://localhost:11434'),
            config=config
        )
    else:
        raise ValueError(f'Unsupported VLM API type selected: {vlm_api}')

    print("VLM Engine configured. Initializing OCREngine.")
    return OCREngine(
        vlm_engine=vlm_engine,
        output_mode=output_format,
        system_prompt=None,
        user_prompt=user_prompt
    )


def process_ocr_request(request):
    """
    Handles the core logic for a SINGLE FILE OCR request.
    This version now uses the configurable TEMP_DIR for its uploads.
    """
    temp_file_path = None
    try:
        if 'input_file' not in request.files:
            raise ValueError("No input file part in request")
        file = request.files['input_file']
        if not file or file.filename == '':
            raise ValueError("No selected file")

        # --- THIS IS THE KEY CHANGE ---
        # Save the file to the configurable temp directory
        filename = secure_filename(file.filename)
        # We use Path() to ensure the join works correctly on any OS
        temp_file_path = str(TEMP_DIR / filename) 
        file.save(temp_file_path)

        ocr_engine = _initialize_ocr_engine(request.form)

        def generate_ocr_stream(ocr_eng, file_to_process_path):
            try:
                for item_dict in ocr_eng.stream_ocr(file_path=file_to_process_path):
                    yield json.dumps(item_dict) + '\n'
            except Exception as e:
                error_obj = {"type": "error", "data": f"Streaming Failed: {str(e)}"}
                yield json.dumps(error_obj) + '\n'
                traceback.print_exc()
            finally:
                # The cleanup_file function will now delete from the correct temp folder
                cleanup_file(file_to_process_path, "post-stream cleanup")

        return Response(stream_with_context(generate_ocr_stream(ocr_engine, temp_file_path)), mimetype='application/x-ndjson')

    except (ValueError, FileNotFoundError) as setup_err:
        if temp_file_path:
            cleanup_file(temp_file_path, "setup error cleanup")
        raise setup_err
    except Exception as setup_err:
        if temp_file_path:
            cleanup_file(temp_file_path, "setup general error cleanup")
        raise Exception(f"Failed during OCR setup: {setup_err}")


def initiate_batch_job(request):
    """
    Saves files and form data for a new batch job and returns the job ID.
    """
    batch_id = str(uuid.uuid4())
    batch_dir = TEMP_DIR / batch_id
    batch_dir.mkdir(exist_ok=True)
    
    # Save form data
    form_data_path = batch_dir / 'form_data.json'
    with open(form_data_path, 'w') as f:
        json.dump(request.form.to_dict(), f)
        
    # Save files
    files = request.files.getlist('batch_input_files')
    if not files or all(f.filename == '' for f in files):
        raise ValueError("No files were provided for batch processing.")
        
    for file in files:
        filename = secure_filename(file.filename)
        file.save(batch_dir / filename)
        
    return batch_id


# In services/web_app/app/app_services.py

def process_batch_ocr_stream(batch_id, base_url):
    """
    Finds a batch job by its ID, processes it, and streams results.
    This function now correctly handles URL generation in the main thread.
    """
    q = queue.Queue()
    # Get a safe reference to the current Flask app object
    app = current_app._get_current_object()

    def run_async_ocr_worker():
        """
        This worker function runs in a separate background thread.
        It is now only responsible for OCR processing.
        """
        # Establish an application context for this background thread
        with app.app_context():
            # Create a new asyncio event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                batch_dir = TEMP_DIR / batch_id
                form_data_path = batch_dir / 'form_data.json'

                if not batch_dir.exists() or not form_data_path.exists():
                    q.put(json.dumps({'type': 'error', 'data': f'Batch job {batch_id} not found.'}))
                    return

                with open(form_data_path, 'r') as f:
                    form_data = json.load(f)

                ocr_engine = _initialize_ocr_engine(form_data)
                output_format_ext_map = {"text": "txt", "markdown": "md", "HTML": "html"}
                output_format = form_data.get('output_format', 'markdown')
                output_format_ext = output_format_ext_map.get(output_format, 'md')
                image_paths = [str(p) for p in batch_dir.iterdir() if p.is_file() and p.suffix.lower() not in ['.json']]

                async def process_and_queue_results():
                    """The async coroutine that calls the OCR library."""
                    response_generator = ocr_engine.concurrent_ocr(
                        file_paths=image_paths, concurrent_batch_size=4
                    )
                    async for result in response_generator:
                        if result.status == "success":
                            output_filename = f"{Path(result.filename).stem}.{output_format_ext}"
                            output_content = result.to_string()
                            with open(batch_dir / output_filename, "w", encoding="utf-8") as f:
                                f.write(output_content)
                            
                            # The worker only sends back the filename for successful results
                            q.put(json.dumps({'type': 'result', 'filename': output_filename}))
                        else:
                            error_data = getattr(result, 'error_message', 'Unknown error.')
                            q.put(json.dumps({'type': 'error', 'filename': Path(result.filename).name, 'data': error_data}))

                loop.run_until_complete(process_and_queue_results())

            except Exception as e:
                print("--- CRITICAL ERROR IN BATCH WORKER THREAD ---")
                traceback.print_exc()
                error_trace = traceback.format_exc()
                q.put(json.dumps({'type': 'error', 'data': f'A critical server error occurred:\n{error_trace}'}))
            finally:
                q.put(None) # Sentinel value to signal completion

    # The base_url is NOT passed to the worker thread
    thread = threading.Thread(target=run_async_ocr_worker)
    thread.start()

    # This loop runs in the main thread with the request context
    while True:
        message_json = q.get()
        if message_json is None:
            yield json.dumps({'type': 'completed', 'batch_id': batch_id})
            break

        message = json.loads(message_json)
        
        # If the message is a successful result, build the URL here
        if message['type'] == 'result':
            relative_url = url_for('download_file', batch_id=batch_id, filename=message['filename'])
            # Combine the base_url from the initial request with the new relative_url
            download_url = f"{base_url.rstrip('/')}{relative_url}"
            message['download_url'] = download_url
            yield json.dumps(message)
        else:
            # For errors or other message types, just pass them along
            yield message_json


def download_processed_file(batch_id, filename):
    """
    Finds a specific processed file within a batch directory and sends it,
    now using a robust method to construct the absolute path.
    """
    try:
        relative_path = TEMP_DIR / str(batch_id) / filename
        absolute_path = Path("/app") / relative_path
        return send_file(absolute_path, as_attachment=True)

    except FileNotFoundError as e:
        current_app.logger.error(f"Caught FileNotFoundError in service: {e}")
        # Re-raise to be caught by the route
        raise e
    except Exception as e:
        current_app.logger.error(f"An unexpected exception occurred in download_processed_file: {e}")
        traceback.print_exc()
        raise e


def download_batch_as_zip(batch_id):
    """
    Zips the processed output files and cleans up the temporary directory
    after the request is complete.
    """
    directory = TEMP_DIR / str(batch_id)
    memory_file = io.BytesIO()
    
    output_extensions = ('.md', '.txt', '.html')

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in directory.iterdir():
            if f.is_file() and (f.name.lower().endswith(output_extensions) or f.name.lower() == "form_data.json"):
                zf.write(f, arcname=f.name)
                
    memory_file.seek(0)

    if not memory_file.getbuffer().nbytes:
        return "No processed files found to download.", 404

    return send_file(
        memory_file,
        download_name=f'batch_results_{batch_id}.zip',
        as_attachment=True,
        mimetype='application/zip'
    )


def render_markdown_text(request):
    """Renders a given text string as HTML."""
    data = request.get_json()
    if 'text' not in data:
        raise ValueError("No text provided for rendering.")
    html = markdown(data['text'], extensions=['fenced_code', 'tables'])
    return jsonify({'status': 'success', 'html': html})


def process_tiff_preview_request(request):
    """Handles a TIFF preview request."""
    temp_file_path = None
    try:
        if 'tiff_file' not in request.files:
            raise ValueError("No tiff_file part in request")
        file = request.files['tiff_file']
        if not file or file.filename == '' or not (file.filename.lower().endswith('.tif') or file.filename.lower().endswith('.tiff')):
            raise ValueError("Invalid TIFF file provided.")

        filename = secure_filename(file.filename)
        temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"preview_{filename}")
        file.save(temp_file_path)

        base64_png_pages = []
        with Image.open(temp_file_path) as img:
            for i in range(img.n_frames):
                img.seek(i)
                page_image = img.convert('RGB')
                buffered = io.BytesIO()
                page_image.save(buffered, format="PNG")
                base64_png_pages.append(base64.b64encode(buffered.getvalue()).decode('utf-8'))
        
        return {'status': 'success', 'pages_data': base64_png_pages, 'format': 'png'}
    finally:
        if temp_file_path:
            cleanup_file(temp_file_path, "tiff preview cleanup")