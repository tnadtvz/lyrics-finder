import os
import requests
import music_tag
import tkinter as tk
from tkinter import filedialog, messagebox
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.id3 import ID3, ID3NoHeaderError
from bs4 import BeautifulSoup
import pyperclip
import eyed3
import time
import random
from dotenv import load_dotenv
from flask import Flask, render_template, url_for, request, jsonify

CMDOutput = ""

load_dotenv()

app = Flask(__name__)

def get_metadata(filepath):
    global CMDOutput
    try:
        _, ext = os.path.splitext(filepath)
        if ext == ".mp3":
            audio = EasyID3(filepath)
            artist = audio.get("artist", [""])[0]
            title = audio.get("title", [""])[0]
            mp3_file = eyed3.load(filepath)
            if mp3_file is not None and mp3_file.tag is not None:
                old_lyrics_frame = mp3_file.tag.frame_set.get(b'USLT')
                old_lyrics = [frame.text for frame in old_lyrics_frame] if old_lyrics_frame is not None else None
            else:
                print("No tag information found for", filepath)
                old_lyrics = None
        elif ext == ".flac":
            audio = FLAC(filepath)
            artist = audio.get("artist", [""])[0]
            title = audio.get("title", [""])[0]
            old_lyrics = audio.tags.get("LYRICS", [])
            old_lyrics = old_lyrics[0] if old_lyrics else None
        else:
            return None

        tags = {"artist": artist, "title": title, "old_lyrics": old_lyrics is not None}
        strTags = str(tags)
        CMDOutput += strTags + "\n"
        return tags

    except (ID3NoHeaderError, NotImplementedError) as e:
        print(f"Error processing file: {filepath}")
        print(f"Error details: {e}")
        return None


def get_lyrics(artist, title):
    global CMDOutput
    base_url = "https://api.genius.com"
    search_url = "/search"

    GENIUS_API_KEY = os.getenv("GENIUS_API_KEY")
    if not GENIUS_API_KEY:
        raise ValueError("Genius API key not found. Set GENIUS_API_KEY environment variable.")
    
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    query = f"{artist} {title}"
    params = {"q": query}

    try:
        response = requests.get(base_url + search_url, params=params, headers=headers)
        response.raise_for_status()
        results = response.json()["response"]["hits"]

        if results:
            song_url = results[0]["result"]["url"]
            print("Genius URL:", song_url)
            GenUrl = "Genius URL:", song_url
            CMDOutput += str(GenUrl) + "\n"

            random_delay = random.uniform(0, 4)
            time.sleep(random_delay)

            lyrics_response = requests.get(song_url)
            lyrics_response.raise_for_status()
            
            soup = BeautifulSoup(lyrics_response.text, "html.parser")
            lyrics_container = soup.find("div", class_="Lyrics-sc-1bcc94c6-1 bzTABU")

            if lyrics_container:
                lyrics_text = lyrics_container.get_text(separator='\n')

                print("Lyrics found:")
                CMDOutput += "Lyrics found:\n"
                print(lyrics_text)
                CMDOutput += lyrics_text + "\n"

                formatted_lyrics = lyrics_text.replace('[', '\n[')
                formatted_lyrics = formatted_lyrics.replace(']', ']\n')

                return formatted_lyrics.strip()

    except requests.exceptions.RequestException as err:
        print("Something went wrong:", err)
        CMDOutput += "Something went wrong\n"


    return None


def delete_lyrics(filepath):
    global CMDOutput
    try:
        f = music_tag.load_file(filepath)
        del f['lyrics']
        f.remove_tag('lyrics')
        f.save()
        print("Lyrics deleted successfully.")
        CMDOutput += "Lyrics deleted successfully\n"
    except Exception as e:
        print(f"Error deleting lyrics: {e}")
        CMDOutput += "Error deleting lyrics: {e}\n"

def add_lyrics(filepath, lyrics):
    global CMDOutput
    try:
        f = music_tag.load_file(filepath)
        f['lyrics'] = lyrics
        f.save()
        print("Lyrics added successfully.")
        CMDOutput += "Lyrics added successfully\n"
    except Exception as e:
        print(f"Error adding lyrics: {e}")


'''def custom_dialog_yes_no(title, prompt):
    root = tk.Tk()
    root.withdraw()

    result = messagebox.askyesno(title, prompt)

    return result'''


def scan_folder(folder_path, action_choice):
    global CMDOutput 
    for dirpath, _, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            metadata = get_metadata(filepath)
            if metadata:
                print(metadata)
                artist = metadata["artist"]
                title = metadata["title"]
                old_lyrics = metadata.get("old_lyrics")
                if action_choice == "yes":
                    lyrics = get_lyrics(artist, title)
                    if lyrics:
                        delete_lyrics(filepath)
                        add_lyrics(filepath, lyrics)
                    else:
                        print("New lyrics not found. Old lyrics preserved.")
                        CMDOutput += "New lyrics not found. Old lyrics preserved.\n"
                elif action_choice == "no":
                    if old_lyrics:
                        print("Old lyrics exist, skipping")
                        CMDOutput += "Old lyrics exist, skipping\n"
                    else:
                        lyrics = get_lyrics(artist, title)
                        add_lyrics(filepath, lyrics)
                else:
                    print("Invalid choice.")

'''folder_path = filedialog.askdirectory()
answer = custom_dialog_yes_no("Lyrics Action", "Do you want to delete the old lyrics first?")
if answer:
    action_choice = "yes"
    scan_folder(folder_path, action_choice)
else:
    action_choice = "no"
    scan_folder(folder_path, action_choice)'''

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_files', methods=['POST'])
def process_files():
    folder_name = request.form['folder_path']
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(base_dir, folder_name)
    if not os.path.exists(folder_path):
        return jsonify({"status": "error", "message": "Folder not found."}), 404
    action_choice = request.form['action_choice']
    scan_folder(folder_path, action_choice)
    return jsonify({"status": "success", "message": "Files processed successfully."})

@app.route('/get_message', methods=['GET'])
def get_message():
    global CMDOutput 
    CMDPackage = CMDOutput
    CMDOutput = "\n"
    return jsonify({"message": CMDPackage})


if __name__ == "__main__":
    app.run(debug=True)
