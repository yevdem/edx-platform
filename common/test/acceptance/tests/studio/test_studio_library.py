"""
Acceptance tests for Content Libraries in Studio
"""
import requests
from .base_studio_test import StudioLibraryTest
from ...pages.studio import BASE_URL
from ...pages.studio.utils import add_component
from ...pages.studio.library import LibraryPage
from ...pages.studio.library_users import LibraryUsersPage


class LibraryEditPageTest(StudioLibraryTest):
    """
    Test the functionality of the library edit page.
    """
    def setUp(self):  # pylint: disable=arguments-differ
        """
        Ensure a library exists and navigate to the library edit page.
        """
        super(LibraryEditPageTest, self).setUp(is_staff=True)
        self.lib_page = LibraryPage(self.browser, self.library_key)
        self.lib_page.visit()
        self.lib_page.wait_until_ready()

    def test_page_header(self):
        """
        Scenario: Ensure that the library's name is displayed in the header and title.
        Given I have a library in Studio
        And I navigate to Library Page in Studio
        Then I can see library name in page header title
        And I can see library name in browser page title
        """
        self.assertIn(self.library_info['display_name'], self.lib_page.get_header_title())
        self.assertIn(self.library_info['display_name'], self.browser.title)

    def test_add_duplicate_delete_actions(self):
        """
        Scenario: Ensure that we can add an HTML block, duplicate it, then delete the original.
        Given I have a library in Studio with no XBlocks
        And I navigate to Library Page in Studio
        Then there are no XBlocks displayed
        When I add Text XBlock
        Then one XBlock is displayed
        When I duplicate first XBlock
        Then two XBlocks are displayed
        And those XBlocks locators' are different
        When I delete first XBlock
        Then one XBlock is displayed
        And displayed XBlock are second one
        """
        self.assertEqual(len(self.lib_page.xblocks), 0)

        # Create a new block:
        add_component(self.lib_page, "html", "Text")
        self.assertEqual(len(self.lib_page.xblocks), 1)
        first_block_id = self.lib_page.xblocks[0].locator

        # Duplicate the block:
        self.lib_page.click_duplicate_button(first_block_id)
        self.assertEqual(len(self.lib_page.xblocks), 2)
        second_block_id = self.lib_page.xblocks[1].locator
        self.assertNotEqual(first_block_id, second_block_id)

        # Delete the first block:
        self.lib_page.click_delete_button(first_block_id, confirm=True)
        self.assertEqual(len(self.lib_page.xblocks), 1)
        self.assertEqual(self.lib_page.xblocks[0].locator, second_block_id)

    def test_add_edit_xblock(self):
        """
        Scenario: Ensure that we can add an XBlock, edit it, then see the resulting changes.
        Given I have a library in Studio with no XBlocks
        And I navigate to Library Page in Studio
        Then there are no XBlocks displayed
        When I add Multiple Choice XBlock
        Then one XBlock is displayed
        When I edit first XBlock
        And I go to basic tab
        And set it's text to a fairly trivial question about Battlestar Galactica
        And save XBlock
        Then one XBlock is displayed
        And first XBlock student content contains at least part of text I set
        """
        self.assertEqual(len(self.lib_page.xblocks), 0)
        # Create a new problem block:
        add_component(self.lib_page, "problem", "Multiple Choice")
        self.assertEqual(len(self.lib_page.xblocks), 1)
        problem_block = self.lib_page.xblocks[0]
        # Edit it:
        problem_block.edit()
        problem_block.open_basic_tab()
        problem_block.set_codemirror_text(
            """
            >>Who is "Starbuck"?<<
             (x) Kara Thrace
             ( ) William Adama
             ( ) Laura Roslin
             ( ) Lee Adama
             ( ) Gaius Baltar
            """
        )
        problem_block.save_settings()
        # Check that the save worked:
        self.assertEqual(len(self.lib_page.xblocks), 1)
        problem_block = self.lib_page.xblocks[0]
        self.assertIn("Laura Roslin", problem_block.student_content)

    def test_no_discussion_button(self):
        """
        Ensure the UI is not loaded for adding discussions.
        """
        self.assertFalse(self.browser.find_elements_by_css_selector('span.large-discussion-icon'))


class LibraryUsersPageTest(StudioLibraryTest):
    """
    Test the functionality of the library "Instructor Access" page.
    """
    def setUp(self):  # pylint: disable=arguments-differ
        """
        Ensure a library exists and navigate to the library edit page.
        """
        super(LibraryUsersPageTest, self).setUp(is_staff=True)

        # Create a second user for use in these tests:
        response = requests.Session().get(BASE_URL + "/auto_auth?username=second&email=second%40example.com&no_login")
        if not response.ok:
            raise RuntimeError("Unable to create required second user.")

        self.page = LibraryUsersPage(self.browser, self.library_key)
        self.page.visit()

    def _expect_refresh(self):
        """
        Wait for the page to reload.
        """
        self.page = LibraryUsersPage(self.browser, self.library_key).wait_for_page()

    def test_user_management(self):
        """
        Scenario: Ensure that we can edit the permissions of users.
        Given I have a library in Studio where I am the only admin
        assigned (which is the default for a newly-created library)
        And I navigate to Library "Instructor Access" Page in Studio
        Then there should be one user listed (myself), and I must
        not be able to remove myself or my instructor privilege.

        When I click Add Intructor
        Then I see a form to complete
        When I complete the form and submit it
        Then I can see the new user is listed as a "User" of the library

        When I click to Add Staff permissions to the new user
        Then I can see the new user has staff permissions and that I am now
        able to promote them to an Admin or remove their staff permissions.

        When I click to Add Admin permissions to the new user
        Then I can see the new user has admin permissions and that I can now
        remove Admin permissions from either user.
        """
        def check_is_only_admin(user):
            """
            Ensure user is an admin user and cannot be removed.
            (There must always be at least one admin user.)
            """
            self.assertIn("admin", user.role_label.lower())
            self.assertFalse(user.can_promote)
            self.assertFalse(user.can_demote)
            self.assertFalse(user.can_delete)
            self.assertTrue(user.has_no_change_warning)
            self.assertIn("Promote another member to Admin to remove admin rights", user.no_change_warning_text)

        self.assertEqual(len(self.page.users), 1)
        user = self.page.users[0]
        self.assertTrue(user.is_current_user)
        check_is_only_admin(user)

        # Add a new user:

        self.assertTrue(self.page.has_add_button)
        self.assertFalse(self.page.new_user_form_visible)
        self.page.click_add_button()
        self.assertTrue(self.page.new_user_form_visible)
        self.page.set_new_user_email('second@example.com')
        self.page.click_submit_new_user_form()

        # Check the new user's listing:

        def get_two_users():
            """
            Expect two users to be listed, one being me, and another user.
            Returns me, them
            """
            users = self.page.users
            self.assertEqual(len(users), 2)
            self.assertEqual(len([u for u in users if u.is_current_user]), 1)
            if users[0].is_current_user:
                return users[0], users[1]
            else:
                return users[1], users[0]

        self._expect_refresh()
        user_me, them = get_two_users()
        check_is_only_admin(user_me)

        self.assertIn("user", them.role_label.lower())
        self.assertTrue(them.can_promote)
        self.assertIn("Add Staff Access", them.promote_btn_text)
        self.assertFalse(them.can_demote)
        self.assertTrue(them.can_delete)
        self.assertFalse(them.has_no_change_warning)

        # Add Staff permissions to the new user:

        them.click_promote()
        self._expect_refresh()
        user_me, them = get_two_users()
        check_is_only_admin(user_me)

        self.assertIn("staff", them.role_label.lower())
        self.assertTrue(them.can_promote)
        self.assertIn("Add Admin Access", them.promote_btn_text)
        self.assertTrue(them.can_demote)
        self.assertIn("Remove Staff Access", them.demote_btn_text)
        self.assertTrue(them.can_delete)
        self.assertFalse(them.has_no_change_warning)

        # Add Admin permissions to the new user:

        them.click_promote()
        self._expect_refresh()
        user_me, them = get_two_users()
        self.assertIn("admin", user_me.role_label.lower())
        self.assertFalse(user_me.can_promote)
        self.assertTrue(user_me.can_demote)
        self.assertTrue(user_me.can_delete)
        self.assertFalse(user_me.has_no_change_warning)

        self.assertIn("admin", them.role_label.lower())
        self.assertFalse(them.can_promote)
        self.assertTrue(them.can_demote)
        self.assertIn("Remove Admin Access", them.demote_btn_text)
        self.assertTrue(them.can_delete)
        self.assertFalse(them.has_no_change_warning)

        # Delete the new user:

        them.click_delete()
        self._expect_refresh()
        self.assertEqual(len(self.page.users), 1)
        user = self.page.users[0]
        self.assertTrue(user.is_current_user)
