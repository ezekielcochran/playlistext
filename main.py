#!venv/bin/python3

import os
from dotenv import load_dotenv
import spotipy
from tqdm import tqdm

# Width of the columns in the output file
TITLE_WIDTH = 50
ARTIST_WIDTH = 40
ID_WIDTH = 22
# Name of folder to store playlist .txt files
PLAYLISTS_FOLDER = "playlists"

# Load .env variables
load_dotenv()

sp = spotipy.Spotify(auth_manager=spotipy.oauth2.SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-private playlist-modify-public"
))

def track_to_str(track) -> str:
    def fit(text: str, length: int) -> str:
        if len(text) > length:
            return text[:length-3] + "..."
        return text.ljust(length)
    name_str = fit(track['name'], TITLE_WIDTH)
    artists = [artist['name'] for artist in track['artists']]
    artists_str = fit(', '.join(artists), ARTIST_WIDTH)
    id_str = track['id']
    assert len(id_str) == ID_WIDTH, f"ID {id_str} is not {ID_WIDTH} characters long"
    return f"{name_str} | {artists_str} | {id_str}"

def track_id_from_str(track_str: str) -> str:
    """
    Get the track ID from a string.
    :param track_str: The string to get the track ID from.
    :return: The track ID.
    """
    return track_str.split('|')[-1].strip()

def get_playlist_tracks(playlist_id:str) -> list:
    """
    Get the tracks in a playlist.
    :param playlist_id: The ID of the playlist to get tracks from.
    :return: A list of tracks in the playlist.
    """
    tracks = []
    chunk_size = 100
    offset = 0

    total_tracks: int = sp.playlist_tracks(playlist_id, limit=1)['total'] # type: ignore
    desc_text = f"Getting {total_tracks} tracks from '{sp.playlist(playlist_id)['name']}'" # type: ignore
    pbar = tqdm(total=total_tracks, unit='tracks', desc=desc_text)

    while offset < total_tracks:
        response: dict = sp.playlist_tracks(playlist_id, limit=chunk_size, offset=offset) # type: ignore
        tracks.extend(response['items'])
        offset += chunk_size
        pbar.update(len(response['items']))

    pbar.close()
    return tracks

def pull_playlist_to_file(playlist_id:str, file_path:str) -> None:
    """
    Write the tracks in a playlist to a file.
    :param playlist_id: The ID of the playlist to get tracks from.
    :param file_path: The path to the file to write the tracks to.
    """
    tracks = get_playlist_tracks(playlist_id)
    with open(file_path, 'w') as f:
        for i, track in enumerate(tracks):
            try:
                f.write(track_to_str(track['track']) + "\n")
            except:
                f.write(f"INVALID TRACK\n")
                print(f"Track {i} seems invalid: {track}")

def set_playlist_tracks(playlist_id:str, track_ids:list) -> None:
    """
    Set the tracks in a playlist.
    :param playlist_id: The ID of the playlist to set tracks for.
    :param track_ids: A list of track IDs to set in the playlist.
    """
    chunk_size = 100
    desc_text = f"Pushing {len(track_ids)} tracks to '{sp.playlist(playlist_id)['name']}'" # type: ignore
    pbar = tqdm(total=len(track_ids), unit='tracks', desc=desc_text)

    chunk = track_ids[:chunk_size]
    track_ids = track_ids[chunk_size:]
    # This one resets the playlist
    sp.playlist_replace_items(playlist_id, chunk)
    pbar.update(len(chunk))

    while len(track_ids) > 0:
        chunk = track_ids[:chunk_size]
        track_ids = track_ids[chunk_size:]

        # TODO Check for invalid IDs... error handling?
        sp.playlist_add_items(playlist_id, chunk)
        pbar.update(len(chunk))

    pbar.close()

def push_playlist_from_file(playlist_id:str, file_path:str) -> None:
    """
    Read the tracks from a file and add them to a playlist.
    :param playlist_id: The ID of the playlist to add tracks to.
    :param file_path: The path to the file to read the tracks from.
    """
    with open(file_path, 'r') as f:
        tracks = f.readlines()
    track_ids = [track_id_from_str(track) for track in tracks]
    set_playlist_tracks(playlist_id, track_ids)

if __name__ == "__main__":
    playlists: dict = sp.current_user_playlists() # type: ignore
    try:
        while True:
            parts = input("Enter a command (pull, push): ").strip().split(None, 1)
            if not parts:
                continue
            command = parts[0].lower()
            playlist_name = parts[1] if len(parts) > 1 else None

            if command == "pull":
                if not playlist_name:
                    playlist_name = input("Enter the name of the playlist to pull: ").strip()
                playlist = next((p for p in playlists['items'] if p['name'] == playlist_name), None) # type: ignore
                if not playlist:
                    print(f"Playlist '{playlist_name}' not found. These are the available playlists:")
                    for p in playlists['items']:
                        print(f"  - {p['name']}")
                    continue
                file_path = os.path.join(PLAYLISTS_FOLDER, f"{playlist['name']}.txt")
                if os.path.exists(file_path):
                    print(f"File {file_path} already exists.")
                    overwrite = input("Would you like to overwrite it? ([y]/n): ").strip().lower()
                    if overwrite not in ['y', 'yes', '']:
                        print("Skipping...")
                        continue
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                pull_playlist_to_file(playlist['id'], file_path)
                print(f"Pulled {playlist_name} to {file_path}")
                continue

            elif command == "push":
                if not os.path.exists(PLAYLISTS_FOLDER):
                    print(f"Folder {PLAYLISTS_FOLDER} does not exist. Please pull a playlist first.")
                    continue
                if not playlist_name:
                    playlist_name = input("Enter the name of the playlist to push: ").strip()
                local_playlists = [
                    os.path.splitext(f)[0]
                    # f
                    for f in os.listdir(PLAYLISTS_FOLDER)
                    if os.path.isfile(os.path.join(PLAYLISTS_FOLDER, f)) and f.endswith('.txt')
                ]
                if playlist_name not in local_playlists:
                    print(f"Playlist '{playlist_name}' not found in local playlists. These are the available playlists:")
                    for p in local_playlists:
                        print(f"  - {p}")
                    continue
                file_path = os.path.join(PLAYLISTS_FOLDER, f"{playlist_name}.txt")
                playlist: dict = next((p for p in playlists['items'] if p['name'] == playlist_name), None) # type: ignore
                push_playlist_from_file(playlist['id'], file_path)
                continue

            else:
                print(f"Invalid command. Please enter 'pull' or 'push'.")
                continue

    except KeyboardInterrupt:
        pass
    except EOFError:
        pass
