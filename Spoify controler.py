# need pip to import library's

import os # used for file directorys
import requests # used for getting info from web through http requests
import serial # used for conecting to the serial com port to comuicate with the arduino
import spotipy # spotifys python API
from spotipy.oauth2 import SpotifyOAuth # this manages the authorization process with Spotify’s API for surcurity
# import serial.tools.list_ports # was used for listing com ports for uses
import time # used for time control like wait function. why isnt this here by defult
from PIL import Image # for covernt and manupulating the image for the arduino "pip install pillow"

class SpotifyHandler:
    def __init__(self, client_id, client_secret, redirect_uri):# set up of the spotify credentails
        self.scope = ( # comands to send to spotify
            "user-read-playback-state "
            "user-modify-playback-state "
            "playlist-modify-public "
            "playlist-modify-private"
        )
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth( # set up of the spotify credentails
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=self.scope
        ))

    def retry_request(self, func, max_retries=3, delay=2): # conects to spotify with buffer
        retries = 0 # number of retries before fail
        while retries < max_retries: # retry to connect if fail
            try:
                return func()
            except spotipy.exceptions.SpotifyException as e:
                print(f"Spotify request failed: {e}")
                retries += 1
                print(f"Retrying... ({retries}/{max_retries})")
                time.sleep(delay)
        print("Max retries exceeded. Spotify might be temporarily unavailable.")
        return None

    def handle_command(self, command): # handles the commands send to and from spotify
        if command == 'next': # if recive "next" message from arduino
            self.sp.next_track() # next song
        elif command == 'previous':# if recive "previous" message from arduino
            self.sp.previous_track()# previous song
        elif command == 'toggle':# if recive "toggle" message from arduino
            playback = self.sp.current_playback() # change playing/pause state
            if playback is not None and playback['is_playing']: # redudency of is not none. use to see if playing of paused and swaped depending on each
                self.sp.pause_playback() # pause if playing
            else:
                self.sp.start_playback()# play if paused
        elif command == 'add_to_playlist':# if recive message from arduino
            # check if the  playlist exists otherwise create it
            user_playlists = self.retry_request(self.sp.current_user_playlists)
            if user_playlists is None: # if failed to create or find playlist
                print("Failed to fetch user playlists.")
                return

            school_playlist = None # set for stating string for if found

            for playlist in user_playlists['items']: # check to see if playlist is found
                if playlist['name'] == 'school':
                    school_playlist = playlist
                    break

            if school_playlist is None: # create playlist if not found
                school_playlist = self.sp.user_playlist_create(user=self.sp.me()['id'], name='school', public=True)# create playlist if not found

            # get the currently playing track
            current_track = self.sp.current_user_playing_track()

            if current_track is not None: # check if song is in playlist
                track_id = current_track['item']['id'] # check if song is in playlist
                self.sp.playlist_add_items(school_playlist['id'], [track_id]) # adds item if not
                print(f"Added track {current_track['item']['name']} to the 'school' playlist.")
            else:
                print("No track is currently playing.")# redudency if no track is active
        elif command == 'remove_from_playlist':# removes song from playlist
            user_playlists = self.retry_request(self.sp.current_user_playlists)# gets current playlist
            if user_playlists is None:
                print("Failed to fetch user playlists.") # redudence for if playlist info not found
                return

            school_playlist = None # set for stating string for if found

            for playlist in user_playlists['items']: # if playlist found
                if playlist['name'] == 'school':
                    school_playlist = playlist # tell playlist is found
                    break

            if school_playlist is not None:
                # get the currently playing track
                current_track = self.sp.current_user_playing_track()

                if current_track is not None:
                    track_id = current_track['item']['id']
                    self.sp.playlist_remove_all_occurrences_of_items(school_playlist['id'], [track_id])# used to remove the song from playlist
                    print(f"Removed track {current_track['item']['name']} from the 'school' playlist.") # info for user
                else:
                    print("No track is currently playing.")
            else:
                print("The 'school' playlist does not exist.")
class SerialHandler: # used to talk to arduiino
    def __init__(self, port, baudrate=115200): # matching same rate as arduino. set to 115200 for more speed
        self.ser = serial.Serial(port, baudrate, timeout=1) # instaises the conection
        time.sleep(2)  # buffor to wait for the serial connection

    def send_message(self, message): # sends info to the arduino
        self.ser.write(message.encode('utf-8'))

    def read_command(self): # reads message coming from arduino
        if self.ser.in_waiting > 0:
            return self.ser.readline().decode('utf-8').strip()
        return None
class ImageHandler:
    @staticmethod
    def download_image(url, filename): # downloads image from spotify
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Image downloaded: {filename}")
        else:
            print(f"Failed to download image: {response.status_code}")

    @staticmethod
    def resize_image(image_path, size=(200, 200)): # reduces the image from 600*600px to 200*200 because thats best size for the arduino
        image = Image.open(image_path) # finds in mage file
        image = image.convert('RGB')  # confirms the image is in RGB mode
        image = image.resize(size, Image.LANCZOS) # resizes it. LANCZOS is the method it downscalled it
        return image

    @staticmethod
    def convert_to_16bit(image): # reduces it from 24 bit to 16 bit to reduce image size
        return [
            [
                (pixel[0] >> 3) << 11 | (pixel[1] >> 2) << 5 | (pixel[2] >> 3)
                for pixel in [image.getpixel((x, y)) for x in range(image.width)]
            ]
            for y in range(image.height)
        ]

    @staticmethod
    def send_pixels(serial_port, pixels, width, height, start_x, start_y): # writes the message to send to the arduino
        serial_port.write(f"{width},{height},{start_x},{start_y}\n".encode('utf-8'))
        for line in pixels:
            line_str = ",".join(f"{color:04X}" for color in line)
            serial_port.write((line_str + "\n").encode('utf-8'))
            while serial_port.read(1) != b'A':
                pass
class App:
    def __init__(self, spotify_client_id, spotify_client_secret, spotify_redirect_uri, serial_port):
        self.spotify = SpotifyHandler(spotify_client_id, spotify_client_secret, spotify_redirect_uri)
        self.serial = SerialHandler(serial_port)
        self.current_track = None

    def update_playlist_status(self, track_id): # used to update if in the playlist
        self.spotify.handle_command('')

    def run(self):  # runs he spotify controler
        while True:
            self.update_progress()
            command = self.serial.read_command()
            if command:
                self.spotify.handle_command(command)
                print(command)

            self.check_playback_status()
            time.sleep(1)

    def update_progress(self): # used to change the progress percentage of the song
        current_playback = self.spotify.retry_request(self.spotify.sp.current_playback)
        if current_playback and current_playback['is_playing']: # check too see if song has change to know when to updae the arduino
            progress_ms = current_playback['progress_ms']
            duration_ms = current_playback['item']['duration_ms']
            progress_percentage = int((progress_ms / duration_ms) * 100)# makes it a percentage
            self.serial.send_message(f'progress:{progress_percentage}\n')# sneds message to arduino
            print(f'Sent progress: {progress_percentage}%')

    def check_playback_status(self): # sets info given by spotify to check later
        playback = self.spotify.sp.current_playback()
        if playback and playback['is_playing']:
            track = playback['item']
            track_name = track['name']
            album_name = track['album']['name']
            artist_names = ', '.join([artist['name'] for artist in track['artists']])
            album_art_url = track['album']['images'][0]['url']
            track_id = track['id']

            if track_name != self.current_track: # check if song has changed
                downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')# download image to downloads
                image_filename = os.path.join(downloads_dir, "active.jpg")# set image as the path in the downloads
                ImageHandler.download_image(album_art_url, image_filename)# set image naem for python to work on it

                self.send_track_info(track_name, album_name, artist_names, image_filename, track_id)
                self.current_track = track_name

    def send_track_info(self, track_name, album_name, artist_names, image_filename, track_id): # ctreate message to send to arduino
        track1, track2 = self.split_string(track_name) # seperates the song name into its parts for arduino
        album1, album2 = self.split_string(album_name) # seperates the album name into its parts for arduino
        artist1, artist2 = self.split_string(artist_names)# seperate the artist name it its parts for arduino
        time.sleep(0.2)
        for message in [track1, track2, album1, album2, artist1, artist2]:# create message for arduino
            print(message)
            self.serial.send_message(f"{message}\n") # sends message
            time.sleep(0.2)

        resized_image = ImageHandler.resize_image(image_filename) # calls class to resize image
        pixels = ImageHandler.convert_to_16bit(resized_image) # calls class to convert image to 16bits
        ImageHandler.send_pixels(self.serial.ser, pixels, resized_image.width, resized_image.height, 7, 54)# sends the message with info to arduino

        self.update_playlist_status(track_id) # check if song is in playlist

    @staticmethod
    def split_string(s):# seperates the names to a mx of 18 charaters per line at max of 2 lines
        max_len = 18 # how many characters per line
        if len(s) <= max_len:  # if less than 18 charaters do nothing
            return s, ""
        elif len(s) <= max_len * 2: # if greater that 18 but less than 32 seperate at 18
            return s[:max_len], s[max_len:]
        else:
            return s[:max_len], s[max_len:max_len * 2] + "..." # if greater than 32 characters split at 18 and add ...
if __name__ == "__main__":
    # my spotify creds
    spotify_client_id = '71075034da754e17b777a73d3fef7a49'
    spotify_client_secret = 'a693c56204f84b288b89452bea07a576'
    spotify_redirect_uri = 'http://localhost:8888/callback' # generric callback
    serial_port = 'COM5' # defult com port for my system

    app = App(spotify_client_id, spotify_client_secret, spotify_redirect_uri, serial_port) # creates a ceonection to spotify
    app.run() # runs app
