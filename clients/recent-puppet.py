"""
Hacky demo tool to pick up the last 2 puppet syncs to production.
"""
import urllib
import urllib2
import json
import os
from pprint import pprint

url = '%s/api/v1/deploy' % os.environ['HISTORY_SERVER_URL']
encoded_args = urllib.urlencode({'environment' : 'production'})
response = urllib2.urlopen(url + "?" + encoded_args).read()


entries  = json.loads(response)
puppets = []
for e in entries:
    if e['thing_name'] == 'puppet' and e['type_of_thing'] == 'config':
        puppets.append(e)

sorted_puppets = sorted(puppets,
                        key=lambda v: v['misc']['timestamp'],
                        reverse=True)
pprint(sorted_puppets[:2])
