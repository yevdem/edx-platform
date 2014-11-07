"""
Content library unit tests that require the CMS runtime.
"""
from contentstore.tests.utils import AjaxEnabledTestClient, parse_json
from contentstore.utils import reverse_url, reverse_usage_url, reverse_library_url
from student.auth import has_studio_read_access, has_studio_write_access
from contentstore.views.tests.test_library import LIBRARY_REST_URL
from student.roles import (
    CourseInstructorRole, CourseStaffRole, CourseCreatorRole, LibraryUserRole,
    OrgStaffRole, OrgInstructorRole, OrgLibraryUserRole,
)
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import ItemFactory
from mock import patch
from opaque_keys.edx.locator import CourseKey, LibraryLocator
import ddt


class LibraryTestCase(ModuleStoreTestCase):
    """
    Common functionality for content libraries tests
    """
    def setUp(self):
        user_password = super(LibraryTestCase, self).setUp()

        self.client = AjaxEnabledTestClient()
        self.client.login(username=self.user.username, password=user_password)

        self.lib_key = self._create_library()
        self.library = modulestore().get_library(self.lib_key)

    def _create_library(self, org="org", library="lib", display_name="Test Library"):
        """
        Helper method used to create a library. Uses the REST API.
        """
        response = self.client.ajax_post(LIBRARY_REST_URL, {
            'org': org,
            'library': library,
            'display_name': display_name,
        })
        self.assertEqual(response.status_code, 200)
        lib_info = parse_json(response)
        lib_key = CourseKey.from_string(lib_info['library_key'])
        self.assertIsInstance(lib_key, LibraryLocator)
        return lib_key

    def _list_libraries(self):
        """
        Use the REST API to get a list of libraries visible to the current user.
        """
        response = self.client.get_json(LIBRARY_REST_URL)
        self.assertEqual(response.status_code, 200)
        return parse_json(response)


#@ddt.ddt
#class TestLibraries(LibraryTestCase):
#    """
#    High-level tests for libraries
#    """
#  ** When rebasing this onto the latest content-libraries branch, put the existing
#     TestLibraries code here and make it inherit from LibraryTestCase


@ddt.ddt
class TestLibraryAccess(LibraryTestCase):
    """
    Test Roles and Permissions related to Content Libraries
    """
    def setUp(self):
        """ Create a library, staff user, and non-staff user """
        super(TestLibraryAccess, self).setUp()
        self.ns_user, self.ns_user_password = self.create_non_staff_user()

    def _login_as_non_staff_user(self, logout_first=True):
        """ Login as a user that starts out with no roles/permissions granted. """
        if logout_first:
            self.client.logout()  # We start logged in as a staff user
        self.client.login(username=self.ns_user.username, password=self.ns_user_password)

    def _assert_cannot_create_library(self, org="org", library="libfail", expected_code=403):
        """ Ensure the current user is not able to create a library. """
        self.assertTrue(expected_code >= 300)
        response = self.client.ajax_post(LIBRARY_REST_URL, {'org': org, 'library': library, 'display_name': "Irrelevant"})
        self.assertEqual(response.status_code, expected_code)
        key = LibraryLocator(org=org, library=library)
        self.assertEqual(modulestore().get_library(key), None)

    def _can_access_library(self, lib_key):
        """ Use the normal studio library URL to check if we have access """
        if not isinstance(lib_key, (basestring, LibraryLocator)):
            lib_key = lib_key.location.library_key
        response = self.client.get(reverse_library_url('library_handler', unicode(lib_key)))
        self.assertIn(response.status_code, (200, 302, 403))
        return response.status_code == 200

    def tearDown(self):
        """
        Log out when done each test
        """
        self.client.logout()
        super(TestLibraryAccess, self).tearDown()

    def test_creation(self):
        """
        The user that creates a library should have instructor (admin) and staff permissions
        """
        # self.library has been auto-created by the staff user.
        self.assertTrue(has_studio_write_access(self.user, self.lib_key))
        self.assertTrue(has_studio_read_access(self.user, self.lib_key))
        # Make sure the user was actually assigned the instructor role and not just using is_staff superpowers:
        self.assertTrue(CourseInstructorRole(self.lib_key).has_user(self.user))

        # Now log out and ensure we are forbidden from creating a library:
        self.client.logout()
        self._assert_cannot_create_library(expected_code=302)  # 302 redirect to login expected

        # Now create a non-staff user with no permissions:
        self._login_as_non_staff_user(logout_first=False)
        self.assertFalse(CourseCreatorRole().has_user(self.ns_user))

        # Now check that logged-in users without any permissions cannot create libraries
        with patch.dict('django.conf.settings.FEATURES', {'ENABLE_CREATOR_GROUP': True}):
            self._assert_cannot_create_library()

    @ddt.data(
        CourseInstructorRole,
        CourseStaffRole,
        LibraryUserRole,
    )
    def test_acccess(self, access_role):
        """
        Test the various roles that allow viewing libraries are working correctly.
        """
        # At this point, one library exists, created by the currently-logged-in staff user.
        # Create another library as staff:
        library2_key = self._create_library(library="lib2")
        # Login as ns_user:
        self._login_as_non_staff_user()

        # ns_user shouldn't be able to access any libraries:
        lib_list = self._list_libraries()
        self.assertEqual(len(lib_list), 0)
        self.assertFalse(self._can_access_library(self.library))
        self.assertFalse(self._can_access_library(library2_key))

        # Now manually intervene to give ns_user access to library2_key:
        access_role(library2_key).add_users(self.ns_user)

        # Now ns_user should be able to access library2_key only:
        lib_list = self._list_libraries()
        self.assertEqual(len(lib_list), 1)
        self.assertEqual(lib_list[0]["library_key"], unicode(library2_key))
        self.assertTrue(self._can_access_library(library2_key))
        self.assertFalse(self._can_access_library(self.library))

    @ddt.data(
        OrgStaffRole,
        OrgInstructorRole,
        OrgLibraryUserRole,
    )
    def test_org_based_access(self, org_access_role):
        """
        Test the various roles that allow viewing all of an organization's
        libraries are working correctly.
        """
        # Create some libraries as the staff user:
        lib_key_pacific = self._create_library(org="PacificX", library="libP")
        lib_key_atlantic = self._create_library(org="AtlanticX", library="libA")

        # Login as a non-staff:
        self._login_as_non_staff_user()

        # Now manually intervene to give ns_user access to all "PacificX" libraries:
        org_access_role(lib_key_pacific.org).add_users(self.ns_user)

        # Now ns_user should be able to access lib_key_pacific only:
        lib_list = self._list_libraries()
        self.assertEqual(len(lib_list), 1)
        self.assertEqual(lib_list[0]["library_key"], unicode(lib_key_pacific))
        self.assertTrue(self._can_access_library(lib_key_pacific))
        self.assertFalse(self._can_access_library(lib_key_atlantic))
        self.assertFalse(self._can_access_library(self.lib_key))

    @ddt.data(True, False)
    def test_read_only_role(self, use_org_level_role):
        """
        Test the read-only role (LibraryUserRole and its org-level equivalent)
        """
        # As staff user, add a block to self.library:
        block = ItemFactory.create(category="html", parent_location=self.library.location, user_id=self.user.id, publish_item=False)

        # Login as a ns_user:
        self._login_as_non_staff_user()
        self.assertFalse(self._can_access_library(self.library))

        block_url = reverse_usage_url('xblock_handler', block.location)

        def can_read_block():
            """ Check if studio lets us view the XBlock in the library """
            response = self.client.get_json(block_url)
            self.assertIn(response.status_code, (200, 403))  # 400 would be ambiguous
            return response.status_code == 200

        def can_edit_block():
            """ Check if studio lets us edit the XBlock in the library """
            response = self.client.ajax_post(block_url)
            self.assertIn(response.status_code, (200, 403))  # 400 would be ambiguous
            return response.status_code == 200

        def can_delete_block():
            """ Check if studio lets us delete the XBlock in the library """
            response = self.client.delete(block_url)
            self.assertIn(response.status_code, (200, 403))  # 400 would be ambiguous
            return response.status_code == 200

        def can_copy_block():
            """ Check if studio lets us duplicate the XBlock in the library """
            response = self.client.ajax_post(reverse_url('xblock_handler'), {
                'parent_locator': unicode(self.library.location),
                'duplicate_source_locator': unicode(block.location),
            })
            self.assertIn(response.status_code, (200, 403))  # 400 would be ambiguous
            return response.status_code == 200

        def can_create_block():
            """ Check if studio lets us make a new XBlock in the library """
            response = self.client.ajax_post(reverse_url('xblock_handler'), {
                'parent_locator': unicode(self.library.location), 'category': 'html',
            })
            self.assertIn(response.status_code, (200, 403))  # 400 would be ambiguous
            return response.status_code == 200

        # Check that we do not have read or write access to block:
        self.assertFalse(can_read_block())
        self.assertFalse(can_edit_block())
        self.assertFalse(can_delete_block())
        self.assertFalse(can_copy_block())
        self.assertFalse(can_create_block())

        # Give ns_user read-only permission:
        if use_org_level_role:
            OrgLibraryUserRole(self.lib_key.org).add_users(self.ns_user)
        else:
            LibraryUserRole(self.lib_key).add_users(self.ns_user)

        self.assertTrue(self._can_access_library(self.library))
        self.assertTrue(can_read_block())
        self.assertFalse(can_edit_block())
        self.assertFalse(can_delete_block())
        self.assertFalse(can_copy_block())
        self.assertFalse(can_create_block())
