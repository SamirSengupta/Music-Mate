from flask import Flask, render_template, request, redirect, url_for, send_file
from pytube import YouTube
import os
import platform
import requests
import re
from youtubesearchpython import VideosSearch
import base64


app = Flask(__name__)

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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']

    try:
        if 'youtube.com' in url:
            # Download from YouTube URL
            video = YouTube(url)
            audio_stream = video.streams.filter(only_audio=True).first()
            output_folder = get_download_folder()
            output_path = os.path.join(output_folder, audio_stream.default_filename)
            audio_stream.download(output_path=output_path)
            return redirect(url_for('download_completed', filename=audio_stream.default_filename))
        elif 'spotify.com' in url:
            # Download from Spotify URL
            track_ids = get_track_ids(url)

            output_folder = get_download_folder()
            for track_id in track_ids:
                # Get the music name from the Spotify API
                music_name = get_music_name(track_id)

                # Search for the music on YouTube
                youtube_url = search_on_youtube(music_name)

                if youtube_url:
                    # Download the audio from YouTube
                    video = YouTube(youtube_url)
                    audio_stream = video.streams.filter(only_audio=True).first()
                    output_path = os.path.join(output_folder, audio_stream.default_filename)
                    audio_stream.download(output_path=output_path)
                else:
                    print(f"No matching video found on YouTube for track ID: {track_id}")

            return redirect(url_for('download_completed', filename=audio_stream.default_filename))
        else:
            return "Invalid URL."

    except Exception as e:
        return f"An error occurred: {str(e)}"


@app.route('/download_completed')
def download_completed():
    filename = request.args.get('filename')
    if filename:
        file_path = os.path.join(get_download_folder(), filename)
        return send_file(file_path, as_attachment=True)
    else:
        return "Download completed."



def get_download_folder():
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.path.expanduser("~"), "Downloads")
    elif system == "Linux":
        return os.path.join(os.path.expanduser("~"), "Downloads")
    elif system == "Darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        raise RuntimeError("Unsupported operating system")


if __name__ == '__main__':
    app.run(debug=False, host = '0.0.0.0')
