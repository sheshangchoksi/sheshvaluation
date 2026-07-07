from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local dev only. In production this is run via gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 5000)))
