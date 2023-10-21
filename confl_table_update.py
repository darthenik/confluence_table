from atlassian import Confluence
from bs4 import BeautifulSoup
import datetime
import gitlab
from dateutil.parser import parse
import os


# private token or personal token authentication
GITLAB_TOKEN = os.environ['GITLAB_TOKEN']
GITLAB_URI = "https://xdevteam.com/"
GITLAB_GROUP = 'se_team'
CONFLUENCE_URI = "https://rest.confluence.softswiss.com"
CONFLUENCE_JWT = os.environ['CONFLUENCE_JWT']


def get_gitlab_users(url, group, token):
    # We will keep track of the number of merge requests per user per month in a dictionary
    merge_requests_data = {}
    group_users = {}

    # Get the current year
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    try:
        gl = gitlab.Gitlab(url=url, private_token=token)
        gl.auth()
        group = gl.groups.get(group)
        group_member_list = group.members.list(all=True)
        # list all projects
        projects = gl.projects.list(all=True)

    except Exception as e:
        print(f"Failed to connect to GitLab: {e}")

    # For each user in the group, get the merge requests they've created for each month of the current year
    for member in group_member_list:
        user = gl.users.get(member.id)
        group_users[user.id] = user.name
        merge_requests_data[user.username] = 0

    # Get the list of project IDs for all projects
    for project in projects:
        # get the list of project members
        members = project.members.list(get_all=True)
        for member in members:
            # check if user is a member of the project
            try:
                if group_users[member.id]:
                    print(f"Proccess user {member.username} in project {project.name}")
                    merge_requests = project.mergerequests.list(author_id=member.id, all=True)
                    for mr in merge_requests:
                        # Check if the merge request was created this year and current month
                        mr_created_date = parse(mr.created_at)
                        if mr_created_date.year == year and mr_created_date.month == month:

                            merge_requests_data[member.username] += 1
            except KeyError:
                pass
    return merge_requests_data


def post_data_to_confluence(url, token, gitlab_users):

    try:

        confluence = Confluence(
            url=url,
            token=token)

        # Get all pages from the space
        space = 'IN'
        page_title = "SE Individual performance"
        page_id = confluence.get_page_id(space, page_title)

        page_content = confluence.get_page_by_id(page_id, expand='body.storage')['body']['storage']['value']

    except Exception as e:
        print(f"Failed to connect to Confluence: {e}")

    # Parse the HTML to find the existing table
    soup = BeautifulSoup(page_content, 'html.parser')
    table = soup.find('table')

    current_month = datetime.datetime.now().strftime('%b')

    # Get the index of the current month's column
    headers = [header.string for header in table.find('tr').find_all('th')]

    # For each user, create a new row with their data for the current month or update the existing one
    for user, value in gitlab_users.items():
        # Find the row for the current user if it exists
        user_row = table.find('td', string=user)

        if user_row is not None:
            # Get all cells in the row
            cells = user_row.find_next_siblings('td')

            # Fetch updated headers
            headers = [header.get_text() for header in table.find_all('th')]

            # Check if a cell for the current month already exists
            if current_month in headers and len(cells) >= headers.index(current_month):
                # Update the value in the cell
                cells[headers.index(current_month) - 1].string = str(value)
        else:
            # If the user doesn't exist, add a new row
            new_row = soup.new_tag('tr')

            # Add the user's name
            new_cell_user = soup.new_tag('td')
            new_cell_user.string = user
            new_row.append(new_cell_user)

            # Add empty cells for past months
            for _ in range(1, headers.index(current_month)):
                new_cell_empty = soup.new_tag('td')
                new_row.append(new_cell_empty)

            # Add the value for the current month
            new_cell_value = soup.new_tag('td')
            new_cell_value.string = str(value)
            new_row.append(new_cell_value)

            table.append(new_row)

    # Update the page with the new table
    confluence.update_page(
        page_id=page_id,
        title=page_title,
        body=str(soup),
        type='page',
        representation='storage'
    )
    print("Table was updated")

gitlab_users = get_gitlab_users(GITLAB_URI, GITLAB_GROUP, GITLAB_TOKEN)

post_data_to_confluence(CONFLUENCE_URI, CONFLUENCE_JWT, gitlab_users)
