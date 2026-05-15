from flask import Flask, render_template

app = Flask(__name__)

# Route für die Startseite
@app.route('/')
def home():
    return render_template('index.html')

# Route für eine reine "Über uns" Seite (falls du später Tabs willst)
@app.route('/about')
def about():
    return render_template('about.html')

# Route für den Driver Hub
@app.route('/hub')
def hub():
    # Lädt jetzt ein richtiges Template für den Hub
    return render_template('hub.html')

if __name__ == '__main__':
    # debug=True startet den Server bei Code-Änderungen automatisch neu
    # Läuft lokal auf Port 6000
    app.run(host='127.0.0.1', port=5005, debug=True)