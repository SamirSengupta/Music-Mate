from flask import Flask, render_template, request, redirect, send_file
import os
from pytube import YouTube
import requests
import re
from youtubesearchpython import VideosSearch
import base64
import firebase_admin
from firebase_admin import credentials, storage
import datetime

app = Flask(__name__)

# Firebase Admin SDK initialization
cred = credentials.Certificate('credentials.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'music-mate-20.appspot.com'
})

bucket = storage.bucket()

# Spotify API credentials
client_id = '0ee393dc28944766855298a4da69e4d4'
client_secret = 'e86ba0783d444176abb20514cefb3674'

# Function to get Spotify access token
def get_access_token():
    # Make a request to the Spotify API to get an access token
    response = requests.post('https://accounts.spotify.com/api/token',
                             headers={'Authorization': 'Basic ' + base64_encode(client_id + ':' + client_secret)},
                             data={'grant_type': 'client_credentials'})
    response.raise_for_status()
    json_response = response.json()
    access_token = json_response['access_token']
    return access_token

# Function to encode client_id and client_secret for Authorization header
def base64_encode(s):
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def get_track_ids(url):
    # Extract the track IDs from the Spotify playlist URL or individual Spotify music URL
    if 'playlist' in url:
        playlist_id = extract_playlist_id(url)
        return get_track_ids_from_playlist(playlist_id)
    elif 'track' in url:
        track_id = extract_track_id(url)
        return [track_id]
    else:
        raise ValueError("Invalid Spotify URL.")

def extract_playlist_id(url):
    # Extract the playlist ID from the Spotify playlist URL
    match = re.search(r'playlist\/([\w]+)', url)
    if match:
        playlist_id = match.group(1)
        return playlist_id
    else:
        raise ValueError("Invalid Spotify playlist URL.")

def extract_track_id(url):
    # Extract the track ID from the individual Spotify music URL
    match = re.search(r'track\/([\w]+)', url)
    if match:
        track_id = match.group(1)
        return track_id
    else:
        raise ValueError("Invalid Spotify music URL.")

def get_track_ids_from_playlist(playlist_id):
    # Get the track IDs from the Spotify playlist using the Spotify API
    access_token = get_access_token()
    response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                            headers={'Authorization': 'Bearer ' + access_token})
    response.raise_for_status()
    json_response = response.json()

    # Extract the track IDs from the API response
    track_ids = [item['track']['id'] for item in json_response['items']]

    return track_ids

def get_music_name(track_id):
    # Get the music name and artist from the Spotify API using the track ID
    access_token = get_access_token()
    response = requests.get(f'https://api.spotify.com/v1/tracks/{track_id}',
                            headers={'Authorization': 'Bearer ' + access_token})
    response.raise_for_status()
    json_response = response.json()

    # Extract the music name and artist from the API response
    music_name = json_response['name']
    artist = json_response['artists'][0]['name']

    # Concatenate the music name and artist for the YouTube search query
    search_query = f"{music_name} {artist}"

    return search_query

def search_on_youtube(query):
    # Search for the given query on YouTube using youtube-search-python
    videos_search = VideosSearch(query, limit=1)
    results = videos_search.result()

    if results['result']:
        # Extract the YouTube URL of the first search result
        youtube_url = results['result'][0]['link']
        return youtube_url

    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']

        try:
            if 'youtube.com' in url:
                # Download from YouTube URL
                video = YouTube(url)
                audio_stream = video.streams.filter(only_audio=True).first()
                file_path = os.path.join(os.path.expanduser('~'), 'Downloads', audio_stream.default_filename)
                audio_stream.download(output_path=os.path.join(os.path.expanduser('~'), 'Downloads'), filename=audio_stream.default_filename)
                # Save the file to Firebase Storage
                firebase_url = save_file_to_firebase(audio_stream.default_filename, file_path)
                return redirect('/')
            elif 'spotify.com' in url:
                # Download from Spotify URL
                track_ids = get_track_ids(url)

                for track_id in track_ids:
                    # Get the music name from the Spotify API
                    music_name = get_music_name(track_id)

                    # Search for the music on YouTube
                    youtube_url = search_on_youtube(music_name)

                    if youtube_url:
                        # Download the audio from YouTube
                        video = YouTube(youtube_url)
                        audio_stream = video.streams.filter(only_audio=True).first()
                        file_path = os.path.join(os.path.expanduser('~'), 'Downloads', audio_stream.default_filename)
                        audio_stream.download(output_path=os.path.join(os.path.expanduser('~'), 'Downloads'), filename=audio_stream.default_filename)
                        # Save the file to Firebase Storage
                        firebase_url = save_file_to_firebase(audio_stream.default_filename, file_path)
                    else:
                        print(f"No matching video found on YouTube for track ID: {track_id}")

                return redirect('/')
            else:
                return "Invalid URL."

        except Exception as e:
            return f"An error occurred: {str(e)}"

    return render_template('index.html')

def save_file_to_firebase(filename, file_path):
    blob = bucket.blob(filename)
    blob.upload_from_filename(file_path)
    download_url = blob.generate_signed_url(
        version='v4',
        expiration=datetime.timedelta(minutes=15),  # Set the expiration time for the URL
        method='GET'
    )
    return download_url

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    # Generate the download URL for the given filename in Firebase Storage
    blob = bucket.blob(filename)
    file_path = os.path.join(os.path.expanduser('~'), 'Downloads', filename)
    blob.download_to_filename(file_path)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)
