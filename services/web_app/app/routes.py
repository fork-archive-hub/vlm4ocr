import os
import traceback
import json
from pathlib import Path
from werkzeug.exceptions import NotFound
from flask import render_template, request, jsonify, Response, stream_with_context, send_from_directory, send_file
from flask import abort, current_app, send_from_directory
from . import app
from . import app_services

@app.route('/')
def index():
    """Renders the main index page with VLM options from app config."""
    vlm_api_options_data = current_app.config.get("vlm_api_options", [])

    return render_template(
        'index.html',
        vlm_api_options=vlm_api_options_data,
    )


@app.route('/api/run_ocr', methods=['POST'])
def handle_ocr_route():
    try:
        # app_services.process_ocr_request returns the fully formed Response object
        response_object = app_services.process_ocr_request(request)
        
        # Directly return the Response object
        return response_object
    
    except ValueError as ve: # Catch setup errors from app_services before streaming starts
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(ve)}), 400
    except Exception as e: # Catch other unexpected setup errors
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': f'An internal server error occurred: {str(e)}'}), 500

@app.route('/api/render_markdown', methods=['POST'])
def handle_render_markdown():
    try:
        response_object = app_services.render_markdown_text(request)
        return response_object
    except Exception as e:
        print(f"--- Unexpected Error in /api/render_markdown route ---")
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': f'An internal server error occurred: {str(e)}'}), 500

@app.route('/api/preview_tiff', methods=['POST'])
def handle_tiff_preview_route():
    """
    Handles the TIFF preview request by calling the service layer function.
    Returns a JSON response with the base64 encoded PNG of the first page or an error.
    """
    print("Request received at /api/preview_tiff route.")
    try:
        result = app_services.process_tiff_preview_request(request)
        return jsonify(result), 200
    except ValueError as ve:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(ve)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': f'An internal server error occurred during TIFF preview: {str(e)}'}), 500

@app.route('/api/initiate_batch_ocr', methods=['POST'])
def handle_initiate_batch_ocr():
    """
    Step 1: Accepts file uploads and form data, saves them, 
    and returns a unique ID for the batch job.
    """
    try:
        batch_id = app_services.initiate_batch_job(request)
        return jsonify({'status': 'success', 'batch_id': batch_id}), 202 # 202 Accepted
    except ValueError as ve:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(ve)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': f'An internal server error occurred: {str(e)}'}), 500

@app.route('/api/stream_batch_results/<batch_id>', methods=['GET'])
def handle_stream_batch_results(batch_id):
    """
    Step 2: Streams the results for a given batch_id using Server-Sent Events.
    """
    def generate_events():
        try:
            url_root = request.url_root 
            for message in app_services.process_batch_ocr_stream(batch_id, url_root):
                yield f"data: {message}\n\n"
        except Exception as e:
            error_message = json.dumps({'type': 'error', 'data': f'An internal server error occurred: {str(e)}'})
            yield f"data: {error_message}\n\n"
            traceback.print_exc()
            
    return Response(stream_with_context(generate_events()), mimetype='text/event-stream')


@app.route('/api/download_file/<batch_id>/<filename>', methods=['GET'])
def download_file(batch_id, filename):
    """
    Handles the file download request by calling the appropriate service function.
    """
    try:
        return app_services.download_processed_file(batch_id, filename)
    except FileNotFoundError as e:
        current_app.logger.error(f"Route caught specific FileNotFoundError: {e}")
        abort(404)
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred during download: {e}")
        traceback.print_exc()
        return "Internal Server Error", 500

@app.route('/api/download_batch_zip/<batch_id>')
def download_batch_zip(batch_id):
    """ Creates a zip archive of all processed files in a batch and sends it. """
    return app_services.download_batch_as_zip(batch_id)