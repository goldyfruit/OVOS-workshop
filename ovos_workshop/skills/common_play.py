from abc import abstractmethod
from ovos_workshop.skills.ovos import OVOSSkill
from ovos_workshop.frameworks.playback import CommonPlayMediaType, CommonPlayMatchConfidence
from ovos_utils.messagebus import Message


class OVOSCommonPlaybackSkill(OVOSSkill):
    """ To integrate with the better common play infrastructure of Mycroft
    skills should use this base class and override
    `CPS_search` (for searching the skill for media to play ) and
    `CPS_play` for launching the media if desired.

    The class makes the skill available to queries from the
    better-playback-control skill and no special vocab for starting playback
    is needed.
    """

    def __init__(self, name=None, bus=None):
        super().__init__(name, bus)
        self.supported_media = [CommonPlayMediaType.GENERIC, CommonPlayMediaType.AUDIO]
        self._current_query = None
        # NOTE: derived skills will likely want to override this list

    def bind(self, bus):
        """Overrides the normal bind method.

        Adds handlers for play:query and play:start messages allowing
        interaction with the playback control skill.

        This is called automatically during setup, and
        need not otherwise be used.
        """
        if bus:
            super().bind(bus)
            self.add_event('ovos.common_play.query', self.__handle_cps_query)
            self.add_event(f'ovos.common_play.{self.skill_id}.play',
                           self.__handle_cps_play)

    def play_media(self, media, disambiguation=None, playlist=None):
        disambiguation = disambiguation or [media]
        playlist = playlist or [media]
        self.bus.emit(Message("ovos.common_play.play",
                              {"media": media,
                               "disambiguation": disambiguation,
                               "playlist": playlist}))

    def __handle_cps_play(self, message):
        self.CPS_play(message.data)

    def __handle_cps_query(self, message):
        """Query skill if it can start playback from given phrase."""
        search_phrase = message.data["phrase"]
        self._current_query = search_phrase
        media_type = message.data.get("question_type", CommonPlayMediaType.GENERIC)

        if media_type not in self.supported_media:
            return

        # invoke the CPS handler to let the skill perform its search
        results = self.CPS_search(search_phrase, media_type)

        if results:
            # inject skill id in individual results, will be needed later
            # for proper VIDEO playback handling
            for idx, r in enumerate(results):
                results[idx]["skill_id"] = self.skill_id
            self.bus.emit(message.response({"phrase": search_phrase,
                                            "skill_id": self.skill_id,
                                            "results": results,
                                            "searching": False}))
        else:
            # Signal we are done (can't handle it)
            self.bus.emit(message.response({"phrase": search_phrase,
                                            "skill_id": self.skill_id,
                                            "searching": False}))

    def CPS_extend_timeout(self, timeout=0.5):
        """ request more time for searching, limits are defined by
        better-common-play framework, by default max total time is 5 seconds
        per query """
        if self._current_query:
            self.bus.emit(Message("ovos.common_play.query.response",
                                  {"phrase": self._current_query,
                                   "skill_id": self.skill_id,
                                   "timeout": timeout,
                                   "searching": True}))

    @abstractmethod
    def CPS_search(self, phrase, media_type):
        """Analyze phrase to see if it is a play-able phrase with this skill.

        Arguments:
            phrase (str): User phrase uttered after "Play", e.g. "some music"
            media_type (CommonPlayMediaType): requested CPSMatchType to search for

        if a result from here is selected with CommonPlayPlaybackType.SKILL then
        CPS_play will be called with result data as argument

        Returns:
            search_results (list): list of dictionaries with result entries
            {
                "match_confidence": CommonPlayMatchConfidence.HIGH,
                "question_type":  CPSMatchType.MUSIC,
                "uri": "https://audioservice.or.gui.will.play.this",
                "playback": CommonPlayPlaybackType.VIDEO,
                "image": "http://optional.audioservice.jpg",
                "bg_image": "http://optional.audioservice.background.jpg"
            }
        """
        return []

    @abstractmethod
    def CPS_play(self, data):
        """Skill was selected for playback

        Playback will be handled manually by the skill, eg, spotify or some
        other external service

        NOTE: CommonPlayPlaybackType.AUDIO and CommonPlayPlaybackType.VIDEO are handled
              automatically by BetterCommonPlay, this is only called for
              CommonPlayPlaybackType.SKILL results

        Arguments:
            data (dict): selected data previously returned in CPS_search

         {
            "match_confidence": CommonPlayMatchConfidence.HIGH,
            "question_type":  CommonPlayMediaType.MUSIC,
            "uri": "https://audioservice.or.gui.will.play.this",
            "playback": CommonPlayPlaybackType.SKILL,
            "image": "http://optional.audioservice.jpg",
            "bg_image": "http://optional.audioservice.background.jpg"
        }
        """
        pass
