#Live link:
https://faseen08.github.io/bus-attendance-face-recognition/

Project: Bus Attendance (Face Recognition)

Quick setup (development):

1. Create and activate a virtualenv (recommended)
   python -m venv .venv
   source .venv/bin/activate

2. Install dependencies
   make install

3. Initialize DB and seed students (dev)
   make initdb
   make seed

4. Start backend and frontend
   make run
   make serve-frontend

Notes:
- Use `python -m backend.app` to run the Flask app in dev. For production use a WSGI server (gunicorn).
- Configure `FRONTEND_ORIGIN` and `DB_PATH` via environment variables or `.env` file.
# bus-attendance-face-recognition
This is a application for automated bus attendance marking system. 
