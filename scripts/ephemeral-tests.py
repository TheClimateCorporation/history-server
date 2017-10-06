#!/usr/bin/env python2.7
import json
import os
import random
import urllib
import urllib2
import unittest

WEB_SERVER_HOST = os.getenv('WEB_SERVER_HOST', 'localhost')
WEB_SERVER_PORT = os.getenv('WEB_SERVER_PORT', '5000')

class TestApi(object):
    server = 'http://{0}:{1}'.format(WEB_SERVER_HOST, WEB_SERVER_PORT)
    maxDiff = None

    @staticmethod
    def random_changeset():
        """
        Return a 40 character string.
        """
        return "".join(
            map(lambda _:
                str(int(random.random() * 10)), xrange(0, 40)))


class TestOverallApi(TestApi, unittest.TestCase):
    def test_propertiez(self):
        # note this is self.server, not self.url (which has the ApiV1 prefix)
        result = json.loads(urllib2.urlopen(self.server + "/propertiez").read())
        # assert we /have/ a version.
        assert result.get('version', None) is not None

    def test_start(self):
        resp = urllib2.urlopen(self.server)
        assert resp.getcode() == 200


class TestApiV1(TestApi, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.prefix = '/api/v1'
        cls.url = cls.server + cls.prefix

    def setUp(self):
        pass

    def url_encode(self, route, args):

        encoded_args = urllib.urlencode(args)
        if route.endswith('/'):
            encoded_url = self.url + route + '/?' + encoded_args
        else:
            encoded_url = self.url + route + '?' + encoded_args

        return encoded_url

    def get_encoded(self, route, args=None):
        if args:
            query = self.url_encode(route, args)
        else:
            query = self.url + route
        return json.loads(urllib2.urlopen(query).read())
    ##############################
    # POSTing needs to be in the superclasses as the different
    # routes/tables interact.

    def post_artifact(self, filename, version_type, version, build_id, misc):
        query_args = {
            'filename' : filename,
            'build_id' : build_id,
            'version' : version,
            'version_type': version_type,
            'misc' : json.dumps(misc)
        }

        encoded_args = urllib.urlencode(query_args)

        response = urllib2.urlopen(self.url + "/artifact", encoded_args).read()
        return response

    def post_build(self,
                   version_type,
                   version,
                   job_url,
                   job_description,
                   duration,
                   result,
                   misc):

        query_args = {
            'version' : version,
            'version_type' : version_type,
            'job_url' : job_url,
            'job_description' : job_description,
            'duration' : duration,
            'result' : result,
            'misc' : json.dumps(misc)
        }

        encoded_args = urllib.urlencode(query_args)

        response = urllib2.urlopen(self.url + "/build", encoded_args).read()
        return response

    def post_promote(self, thing_type, thing, environment, misc):
        query_args = {
            'thing_type' : thing_type,
            'thing_name' : thing,
            'environment' : environment,
            'misc' : json.dumps(misc)
        }
        encoded_args = urllib.urlencode(query_args)

        response = urllib2.urlopen(self.url + "/promote", encoded_args).read()
        return response

    def post_deploy(self,
                    thing_type,
                    thing_name,
                    version_type,
                    version,
                    environment,
                    servername,
                    misc):
        query_args = {
            'thing_type' : thing_type,
            'thing_name' : thing_name,
            'environment' : environment,
            'version_type' : version_type,
            'version' : version,
            'misc' : json.dumps(misc)
        }

        if servername:
            query_args['servername'] = servername

        encoded_args = urllib.urlencode(query_args)

        response = urllib2.urlopen(self.url + "/deploy", encoded_args).read()
        return response


class TestSwaggerDocs(TestApiV1):

    def test_swagger_docs(self):
        resp = urllib2.urlopen(self.url + "/swagger")
        assert resp.getcode() == 200


class TestAPIV1Build(TestApiV1):

    @staticmethod
    def _strip_returned_builds_of_noise(build):
        # remove detrius from the database
        for attr in ('build_id', 'duration', 'insertion_time', 'version_id'):
            if attr in build:
                del build[attr]

    def test_build_empty(self):
        try:
            resp = urllib2.urlopen(self.url + "/build")
        except urllib2.HTTPError as e:
            if e.getcode() == 409:
                pass
            else:
                raise
        else:
            raise

    def test_build(self):
        test_changeset = TestApi.random_changeset()
        test_url = 'http://example.com/test-' + str(int(random.random() * 10000))
        build_id = self.post_build('changeset',
                                   test_changeset,
                                   test_url,
                                   'a test',
                                   10,
                                   'true',
                                   {"whisky" : "scotch", "beer" : "horses"})

        # These all should return 1 entry

        url_resp = self.get_encoded("/build", {"job_url" : test_url})

        chng_resp = self.get_encoded("/build", {"version_type" : 'changeset',
                                                'version' : test_changeset})

        id_resp = self.get_encoded("/build", {"build_id" : build_id})

        self.assertItemsEqual(url_resp, chng_resp)
        self.assertItemsEqual(id_resp, chng_resp)

        more_id_resp = self.get_encoded("/build/{0}".format(build_id))
        self.assertItemsEqual(more_id_resp, chng_resp)

        search_resp = self.get_encoded("/build/search", {"build_id" : build_id})
        TestAPIV1Build._strip_returned_builds_of_noise(search_resp['builds'][0])
        TestAPIV1Build._strip_returned_builds_of_noise(chng_resp[0])
        self.assertItemsEqual(search_resp.get('builds'), chng_resp)

        build_id = self.post_build('package',
                                   "v1.2.3",
                                   test_url,
                                   'a test once more',
                                   12,
                                   'maybe',
                                   {})


        query_url = self.get_encoded("/build/all")

class TestAPIV1Artifact(TestApiV1):

    @staticmethod
    def _strip_returned_artifacts_of_noise(artifact):
        # remove detrius from the database
        for attr in ('build_id', 'artifact_id', 'thing_id', 'version_id', 'thing_type', 'insertion_time'):
            if attr in artifact:
                del artifact[attr]


    def test_artifact(self):
        # this test carries with it a dependency on POST /build
        # working, since artifacts require a FK out to builds.

        test_changeset = TestApi.random_changeset()
        test_filename = "/tmp/testfilename-" + str(int(random.random() * 10000))
        test_filename2 = "/tmp/othertestfilename-" + str(int(random.random() * 10000))

        test_url = 'http://example.com/artifacts/test-' + str(int(random.random() * 10000))
        build_id = self.post_build('changeset',
                                   test_changeset,
                                   test_url,
                                   'a test',
                                   20,
                                   'successful',
                                   {'comment' : 'test of artifact insertion'})
        artifact_id_1 = self.post_artifact(test_filename,
                                           'changeset',
                                           test_changeset,
                                           build_id,
                                           {'comment' : 'an artifact getting tested'})
        self.assertIsNotNone(artifact_id_1)

        # another artifact came from this build!
        artifact_id_2 = self.post_artifact(test_filename2,
                                           'changeset',
                                           test_changeset,
                                           build_id,
                                           {'comment' : 'another artifact getting tested'})
        self.assertIsNotNone(artifact_id_2)

        # expect one artifact
        artifact_1_list = self.get_encoded("/artifact",
                                           {'filename' : test_filename})

        self.assertEqual(len(artifact_1_list), 1)
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(artifact_1_list[0])

        # we reuse this record further on.
        expected_record_1 = {'version_type' : 'changeset',
                             'version' : test_changeset,
                             'job_url' : test_url,
                             'unique_thing_name' : test_filename,
                             'duration' : 20,
                             'result' : 'successful',
                             'misc' : {'comment' : 'an artifact getting tested'},
                             'job_description' : 'a test'}

        self.assertItemsEqual(expected_record_1, artifact_1_list[0])

        # expect one artifact
        artifact_2_list = self.get_encoded("/artifact",
                                           {'filename' : test_filename2})
        self.assertEqual(len(artifact_2_list), 1)
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(artifact_2_list[0])
        expected_record_2 = {'version' : test_changeset,
                             'version_type' : 'changeset',
                             'job_url' : test_url,
                             'unique_thing_name' : test_filename2,
                             'duration' : 20,
                             'result' : 'successful',
                             'misc' : {'comment' : 'another artifact getting tested'},
                             'job_description' : 'a test'}
        self.assertItemsEqual(expected_record_2, artifact_2_list[0])

        # expect two artifacts
        artifact_changeset_list = self.get_encoded("/artifact",
                                                   {'version' : test_changeset,
                                                    'version_type' : 'changeset'})
        self.assertEqual(len(artifact_changeset_list), 2)
        map(TestAPIV1Artifact._strip_returned_artifacts_of_noise, artifact_changeset_list)

        self.assertItemsEqual(artifact_changeset_list, [expected_record_1, expected_record_2])

        # expect same two artifacts
        build_id_list = self.get_encoded("/artifact",
                                         {'build_id' : build_id})
        self.assertEqual(len(build_id_list), 2)
        map(TestAPIV1Artifact._strip_returned_artifacts_of_noise, build_id_list)
        self.assertItemsEqual(build_id_list, [expected_record_1, expected_record_2])

        # expect one artifact
        artifact_id_1_list = self.get_encoded("/artifact",
                                              {'artifact_id' : artifact_id_1})
        self.assertEqual(len(artifact_id_1_list), 1)
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(artifact_id_1_list[0])
        self.assertEqual(artifact_id_1_list[0], expected_record_1)

        # expect one artifact
        artifact_id_2_list = self.get_encoded("/artifact",
                                              {'artifact_id' : artifact_id_2})
        self.assertEqual(len(artifact_id_2_list), 1)
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(artifact_id_2_list[0])
        self.assertEqual(artifact_id_2_list[0], expected_record_2)

        artifact_id_3_list = self.get_encoded("/artifact/{0}".format(artifact_id_2))
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(artifact_id_3_list[0])
        self.assertEqual(artifact_id_3_list[0], expected_record_2)

        searched_artifact = self.get_encoded("/artifact/search",
                                              {'artifact_id' : artifact_id_2})
        TestAPIV1Artifact._strip_returned_artifacts_of_noise(searched_artifact.get('artifacts')[0])
        self.assertEqual(searched_artifact.get('artifacts')[0], expected_record_2)

class TestAPIV1Promote(TestApiV1):

    @staticmethod
    def _strip_returned_promotes_of_noise(promote):
        for attr in ('promote_id', 'promotion_time', 'thing_time'):
            if attr in promote:
                del promote[attr]


    def test_git_repo_thing(self):
        test_changeset = TestApi.random_changeset()
        test_repo = "gopher://repo.git"
        promote_id = self.post_promote('git_repo',
                                       test_repo,
                                       'qa',
                                       { 'desc' : 'a test only a test' })
        self.assertIsNotNone(promote_id)

    def test_promote(self):
        test_changeset = TestApi.random_changeset()
        test_filename = "/tmp/testfilename-" + str(int(random.random() * 10000))

        test_url = 'http://example.com/artifacts/test-' + str(int(random.random() * 10000))
        build_id = self.post_build('changeset',
                                   test_changeset,
                                   test_url,
                                   'a test',
                                   20,
                                   'true',
                                   {'comment' : 'test of promote insertion'})
        self.assertIsNotNone(build_id)

        artifact_id = self.post_artifact(test_filename,
                                         'changeset',
                                         test_changeset,
                                         build_id,
                                         {'comment' : 'an artifact getting towards promote'})
        self.assertIsNotNone(artifact_id)

        # testing begins.

        environment = "qa"
        qa_promote_id = self.post_promote('filename',
                                           test_filename,
                                           environment,
                                           {"comment" : "starting in qa"})
        environment = "production"
        production_promote_id = self.post_promote('filename',
                                                  test_filename,
                                                  environment,
                                                  {"comment" : "promoted to production"})
        assert production_promote_id is not None

        expected_qa_promote = {
            "environment" : "qa",
            "thing_name" : test_filename,
            "thing_type" : 'filename',
            "misc": {"comment" : "starting in qa"}}

        expected_production_promote = {
            "environment" : "production",
            "thing_name" : test_filename,
            "thing_type" : 'filename',
            "misc" : {"comment" : "promoted to production"}
        }

        all_promotes_from_file = self.get_encoded("/promote",
                                                  {'thing_type' : 'filename',
                                                   'thing_name': test_filename})


        map(TestAPIV1Promote._strip_returned_promotes_of_noise, all_promotes_from_file)
        self.assertItemsEqual([expected_qa_promote, expected_production_promote],
                              all_promotes_from_file)

        prod_promote = self.get_encoded("/promote",
                                        {'promote_id': production_promote_id})
        self.assertEqual(len(prod_promote), 1)
        TestAPIV1Promote._strip_returned_promotes_of_noise(prod_promote[0])
        self.assertEqual(prod_promote[0], expected_production_promote)


        prod_promote_2 = self.get_encoded("/promote/{0}".format(production_promote_id))
        self.assertEqual(len(prod_promote_2), 1)
        TestAPIV1Promote._strip_returned_promotes_of_noise(prod_promote_2[0])
        self.assertEqual(prod_promote_2[0], expected_production_promote)

        # note: promote?environment= ... is going to return varying results,
        # depending on what we have already run. Since an ideal test
        # suite runs in different orders, we will test that our
        # promote *exists*, but not that our list of promotes in an
        # environment is the totality of promotes that the server
        # knows.

        some_qa_promotes = self.get_encoded("/promote",
                                                 {"environment" : "qa"})
        map(TestAPIV1Promote._strip_returned_promotes_of_noise, some_qa_promotes)
        self.assertIn(expected_qa_promote, some_qa_promotes)

        some_production_promotes = self.get_encoded("/promote",
                                                 {"environment" : "production"})

        map(TestAPIV1Promote._strip_returned_promotes_of_noise, some_production_promotes)
        self.assertIn(expected_production_promote, some_production_promotes)


class TestApiV1Deploy(TestApiV1):

    @staticmethod
    def _strip_returned_deploys_of_noise(deploy):
        for attr in ('deploy_id', 'insertion_time', 'version_id'):
            if attr in deploy:
                del deploy[attr]
        return deploy

    def test_extra_environments(self):
        test_changeset1 = TestApi.random_changeset()
        test_name1 = "test-artifact-" + str(int(random.random() * 10000))
        # picked out a few candidates for problems
        for env in ['production', 'qa', 'system']:
            self.post_deploy('filename',
                             test_name1,
                             'changeset',
                             test_changeset1,
                             env,
                             None,
                             {})

    def test_deploy(self):
        thing_type_list = ('filename', 'config', 'dockerimage')

        test_changeset1 = TestApi.random_changeset()
        test_changeset2 = TestApi.random_changeset()
        test_changeset3 = TestApi.random_changeset()

        test_name1 = "test-thing-" + str(int(random.random() * 10000))
        test_name2 = "test-thing-" + str(int(random.random() * 10000))
        test_name3 = "test-thing-" + str(int(random.random() * 10000))


        deploy_1_config_id = self.post_deploy('config',
                                              test_name1,
                                              'changeset',
                                              test_changeset1,
                                              'system',
                                              None,
                                              {
                                                  "comment" : "this is another test"
                                              })

        deploy_2_config_id = self.post_deploy('config',
                                              test_name1,
                                              'changeset',
                                              test_changeset1,
                                              'qa',
                                              None,
                                              {
                                                  "comment" : "this is a continued test"
                                              })

        deploy_1_expected_result = {
            u'thing_type' : u'config',
            u'thing_name' : unicode(test_name1),
            u'version_type' : u'changeset',
            u'version' : unicode(test_changeset1),
            u'environment' : u'system',
            u'servername': None,
            u'misc' : {
                u"comment" : u"this is another test"
            }}

        deploy_2_expected_result = {
            'thing_type' : 'config',
            'thing_name' : test_name1,
            'version_type' : 'changeset',
            'version' : test_changeset1,
            'environment' : 'qa',
            'servername': None,
            'misc' : {
                "comment" : "this is a continued test"
            }}
        test = self.get_encoded('/deploy',
                                {
                                    'version' : test_changeset1,
                                    'version_type' : 'changeset'
                                })
        got = sorted(
            map(
                TestApiV1Deploy._strip_returned_deploys_of_noise,
                self.get_encoded('/deploy',
                                 {
                                     'version' : test_changeset1,
                                     'version_type': 'changeset'
                              })))
        wanted = sorted([deploy_1_expected_result,
                         deploy_2_expected_result])
        self.assertItemsEqual(wanted, got)

        # some stuff should come back. We vet we get the stuff we put
        # in.
        all_deploys = self.get_encoded("/deploy/all")
        map(TestApiV1Deploy._strip_returned_deploys_of_noise, all_deploys)
        self.assertIn(deploy_1_expected_result, all_deploys)
        self.assertIn(deploy_2_expected_result, all_deploys)

        # verify ?deploy-id=
        got = TestApiV1Deploy._strip_returned_deploys_of_noise(
            self.get_encoded('/deploy', {'deploy_id' : deploy_2_config_id})[0])
        self.assertEqual(deploy_2_expected_result, got)

        api_resource_got = self.get_encoded("/deploy/{0}".format(deploy_2_config_id))[0]
        TestApiV1Deploy._strip_returned_deploys_of_noise(api_resource_got)
        self.assertEqual(deploy_2_expected_result, api_resource_got)

        # verify ?changeset=
        self.post_deploy('filename',
                         test_name2,
                         'changeset',
                         test_changeset2,
                         'production',
                         None,
                         {
                             "comment" : "this is a continued test"
                         })

        got = self.get_encoded('/deploy', {
            'version_type' : 'changeset',
            'version' : test_changeset2})
        self.assertEqual(len(got), 1)
        got = TestApiV1Deploy._strip_returned_deploys_of_noise(got[0])
        expected_prod_deploy = {u'thing_type' : u'filename',
                                u'thing_name' : unicode(test_name2),
                                u'version_type' : u'changeset',
                                u'version' : unicode(test_changeset2),
                                u'environment' : u'production',
                                u'servername' : None,
                                u'misc' : {u"comment" : u"this is a continued test"}}

        self.assertEqual(expected_prod_deploy,
                              got)

        # verify ?environment=
        got = map(TestApiV1Deploy._strip_returned_deploys_of_noise,
                  self.get_encoded('/deploy', {'environment' : 'production'}))

        self.assertIn(expected_prod_deploy, got)

        self.post_deploy('filename',
                         test_name2,
                         'changeset',
                         test_changeset2,
                         'system',
                         None,
                         {
                             "comment" : "this is a continued test"
                         })

        # verify ?thing-name=
        got = map(TestApiV1Deploy._strip_returned_deploys_of_noise,
                  self.get_encoded('/deploy', {'thing_name' : test_name2}))
        assert len(got) == 2
        self.assertIn(expected_prod_deploy, got)

        version = "v-" + str(int(random.random() * 10000))
        expected_result = {
            'thing_type' : 'filename',
            'thing_name' : 's4:/some-artifact.deb',
            'version_type' : 'package',
            'version' : version,
            'environment' : 'system',
            'servername' : 'ten.example.com',
            'misc' : {
                "comment" : "package"
            }
        }


        deploy_4_config_id = self.post_deploy('filename',
                                              's4:/some-artifact.deb',
                                              'package',
                                              version,
                                              'system',
                                              'ten.example.com',
                                              {
                                                  "comment" : "package"
                                              })
        got = self.get_encoded('/deploy',
                               {
                                   'version_type' : 'package',
                                   'version' : version
                               })
        assert len(got) == 1
        del got[0]['deploy_id']
        del got[0]['version_id']
        del got[0]['insertion_time']
        self.assertEqual(got[0], expected_result)


        got_search = self.get_encoded('/deploy/search',  {
                                   'version_type' : 'package',
                                   'version' : version
                               })
        assert len(got) == 1
        del got_search.get('deploys')[0]['deploy_id']
        del got_search.get('deploys')[0]['version_id']
        del got_search.get('deploys')[0]['insertion_time']
        self.assertEqual(got_search.get('deploys')[0], expected_result)

class TestSearch(TestApiV1):

    # Tests for enhanced search features (wildcard, comparators)
    def test_search_wildcard(self):
        self.post_deploy('filename',
                         'test_name1',
                         'changeset',
                          TestApi.random_changeset(),
                         'system',
                         None,
                         {
                             "comment" : "this is a continued test"
                         })

        self.post_deploy('filename',
                         'test_name2',
                         'package',
                          TestApi.random_changeset(),
                         'qa',
                         None,
                         {
                             "comment" : "this is a continued test"
                         })

        got_search = self.get_encoded('/deploy/search',  {
                                   'version_type' : 'change*',
                               })

        assert len(got_search) == 1
        self.assertEqual(got_search['deploys'][0]['version_type'], 'changeset')

    def test_search_comparator(self):
        test_changeset = TestApi.random_changeset()
        test_url = 'http://example.com/test-' + str(int(random.random() * 10000))
        self.post_build('changeset',
                        test_changeset,
                        test_url,
                        'a test',
                        10,
                        'true',
                        {'foo' : 'bar', 'macaroni' : 'cheeses'})

        self.post_build('changeset',
                        test_changeset,
                        test_url,
                        'a test',
                        9,
                        'true',
                        {'foo' : 'bar', 'macaroni' : 'cheeses'})

        self.post_build('changeset',
                        test_changeset,
                        test_url,
                        'a test',
                        7,
                        'true',
                        {'foo' : 'bar', 'macaroni' : 'cheeses'})

        got_search = self.get_encoded('/build/search',  {
                                   'duration' : '<8',
                               })

        self.assertEqual(len(got_search['builds']), 1)

        got_search2 = self.get_encoded('/build/search',  {
                                   'duration' : '<=9',
                               })
        assert len(got_search2['builds']) == 2

        got_search3 = self.get_encoded('/build/search',  {
                                   'duration' : '<=9,>7',
                               })

        assert len(got_search3['builds']) == 1

        self.assertEqual(got_search['builds'][0]['duration'], 7)

if __name__ == '__main__':
    unittest.main()
