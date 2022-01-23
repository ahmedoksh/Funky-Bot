import requests
import re
from pytube import YouTube

class YoutubeAPI:
    def __init__(self):
        self.base_search_url = "https://www.youtube.com/results?q="
        self.base_video_url = "https://www.youtube.com/watch?v="

    # get_top_search_results returns a list of urls for the most relevant videos.
    def get_top_search_results(self, video_title):
        encoded_url = self.base_search_url + requests.utils.quote(video_title)

        response = requests.get(url=encoded_url)
        if response.status_code != 200:
            raise Exception("Unexpected status code: %d".format(response.status_code))

        matches = re.findall(r'watch\?v=(.+?)"', response.text)
        return [self.base_video_url + video_id for video_id in matches]

    def get_first_title(self, search_title):
        first_link = self.get_top_search_results(search_title)[0]
        return YouTube(first_link).title