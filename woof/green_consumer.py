from gevent import monkey; monkey.patch_all()
import threading, logging, gevent, time

from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
log = logging.getLogger("kafka")

class GreenFeedConsumer(threading.Thread):
    """
    Greenlet based feed consumer
    All callbacks are spawned as greenlets on a background thread


    keyword arguments :

    broker (list): List of initial broker nodes the consumer should contact to
    bootstrap initial cluster metadata.  This does not have to be the full node list.
    It just needs to have at least one broker

    group (str): the name of the consumer group to join, Offsets are fetched /
    committed to this group name.

    offset='smallest' : read all msgs from beginning of time;  default read fresh

    commit_every_t_ms:  How much time (in milliseconds) to before commit to zookeeper

    """
    daemon = True
    
    def __init__(self, broker, group, offset='largest', commit_every_t_ms=1000,
                 parts=None):
        self.brokerurl = broker
        try:
            self.cons = KafkaConsumer(bootstrap_servers=broker,
                                      auto_offset_reset=offset,
                                      auto_commit_enable=True,
                                      auto_commit_interval_ms=commit_every_t_ms,
                                      group_id=group
                                      )
        except KafkaUnavailableError:
            log.critical( "\nCluster Unavailable %s : Check broker string\n", broker)
            raise
        except:
            raise

        self.topics = []
        self.callbacks = {}
        super(GreenFeedConsumer, self).__init__()

    def add_topic(self, topic, todo , parts=None):
        """
        Set the topic/partitions to consume

        todo (callable) : callback for the topic
        NOTE: Callback is for entire topic, if you call this for multiple
        partitions for same topic with diff callbacks, only the last callback
        is retained

        topic : topic to listen to

        parts (list) : tuple of the partitions to listen to

        """
        self.callbacks[topic] = todo

        if parts is None:
            log.info(" GreenConsumer : adding topic %s ", topic)
            self.topics.append(topic)
        else:
              for part in parts:
                  log.info(" GreenConsumer : adding topic %s %s", topic , part)
                  self.topics.append((topic,part))

        self.cons._client.ensure_topic_exists(topic)
        self.cons.set_topic_partitions(*self.topics)

    def remove_topic(self, topic,  parts=None):
        try:

            if parts is None:
                self.topics.remove(topic)
            else:
                for part in parts:
                    self.topics.remove((topic,part))
        except:
            log.critical("GreenConsumer : no such topic %s", topic)
            return
        log.info(" GreenConsumer : removed topic %s", topic)
        self.cons.set_topic_partitions(*self.topics)

    def wrap(self, callback, mesg):
        callback(mesg.key, mesg.value)
        self.cons.task_done(mesg)

    def run(self):
        while True:
            try:
                for m in self.cons.fetch_messages():
                    gevent.spawn(self.wrap, self.callbacks[m.topic], m)
            except:
                time.sleep(1)
                continue
