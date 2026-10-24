#!/usr/bin/env bash

if [ "$1" == "--run" ]; then
    echo "Starting Meeting Intelligence backend..."
    # Run backend in the background
    .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &
    BACKEND_PID=$!

    echo "Starting Meeting Intelligence frontend..."
    # Run frontend in the background
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    
    # Cleanup function to kill both processes on exit
    cleanup() {
        echo ""
        echo "Shutting down application..."
        kill $FRONTEND_PID 2>/dev/null || true
        kill $BACKEND_PID 2>/dev/null || true
        echo "Application stopped successfully."
        exit 0
    }
    
    # Trap Ctrl+C (SIGINT) and termination (SIGTERM)
    trap cleanup SIGINT SIGTERM
    
    echo ""
    echo "🚀 Application is running!"
    echo "- Backend: http://127.0.0.1:8000"
    echo "- Frontend: http://localhost:5173"
    echo "Press Ctrl+C to stop both services."
    echo ""
    
    # Wait keeps the script running until you hit Ctrl+C
    wait
else
    echo "Usage: ./app.sh --run"
    exit 1
fi
