import requests
import re
from pytube import YouTube
from typing import List

class YoutubeAPI:
    """A class used to interact with the YouTube API"""
    def __init__(self) -> None:
        """Initializes a new instance of the YoutubeAPI class."""
        self.base_search_url = "https://www.youtube.com/results?q="
        self.base_video_url = "https://www.youtube.com/watch?v="

    # get_top_search_results returns a list of urls for the most relevant videos.
    def get_top_search_results(self, video_title: str) ->  List[str]:
        """Returns a list of URLs for the most relevant videos.
        Args:
            video_title (str): The title of the video to search for.
        Returns:
            List[str]: A list of URLs for the most relevant videos.
        """
        encoded_url = self.base_search_url + requests.utils.quote(video_title)

        response = requests.get(url=encoded_url)
        if response.status_code != 200:
            raise Exception("Unexpected status code: %d".format(response.status_code))

        matches = re.findall(r'watch\?v=(.+?)"', response.text)
        return [self.base_video_url + video_id for video_id in matches]

    def get_first_title(self, search_title: str) -> str:
        """Takes a search title and returns the title of the first video in the search results.
        Args:
            search_title (str): The title of the video to search for.
        Returns:
            str: The title of the first video in the search results.
        """
        first_link = self.get_top_search_results(search_title)[0]
        return YouTube(first_link).title