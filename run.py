from app import create_app

app = create_app()

if __name__ == "__main__":
    # start the development server
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])
