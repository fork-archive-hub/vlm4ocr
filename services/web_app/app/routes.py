import traceback
from flask import render_template, request, jsonify, Response, stream_with_context
from . import app
from . import app_services

@app.route('/')
def index():
    """Renders the main index page with VLM options from app config."""
    vlm_api_options_data = app.app_config.get("vlm_api_options", [])

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

@app.route('/api/run_batch_ocr', methods=['POST'])
def handle_batch_ocr_route():
    try:
        # This service will handle multiple files and return a zipped response
        response_object = app_services.process_batch_ocr_request(request)
        return response_object
    except ValueError as ve:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(ve)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': f'An internal server error occurred: {str(e)}'}), 500