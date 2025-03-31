# PDF to Questions Web Application

This web application allows users to upload PDF files and automatically extract questions from them using Google's Gemini AI. The extracted questions are then formatted and provided in an Excel file.

## Features

- PDF file upload
- Automatic question extraction using Gemini AI
- Progress tracking for extraction process
- Excel file download of extracted questions
- Real-time status updates

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key
- `PORT`: (Optional) Port number for the web server (default: 5000)

## Project Structure

- `app.py`: Main Flask application
- `pdf_to_questions.py`: Core question extraction logic
- `templates/`: HTML templates
- `static/`: Static files (CSS, JS, etc.)
- `uploads/`: Temporary storage for uploaded PDFs
- `results/`: Storage for generated Excel files

## Deployment

This application is configured for deployment on Render.com using the included `render.yaml` configuration file. 