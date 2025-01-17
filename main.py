#
# This is the "server" and should run on your FD station with an Internet connection.
#
import asyncio
import configparser
import os
import websockets
import json
import sys
import requests
from markdown_it import MarkdownIt
from mdit_plain.renderer import RendererPlain
import imaplib
import email
from email.header import decode_header
import base64
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def encode_file_to_base64_string(input_file):
    with open(input_file, 'rb') as file:
        file_content = file.read()
        encoded_bytes = base64.b64encode(file_content)
        encoded_string = encoded_bytes.decode('utf-8')
    return encoded_string


def decode_base64_to_file(encoded_string, output_file):
    decoded_bytes = base64.b64decode(encoded_string)
    with open(output_file, 'wb') as file:
        file.write(decoded_bytes)


def fetch_filtered_emails(search_email=None, search_subject=None, retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)

            # Login to the account
            mail.login(IMAP_USERNAME, IMAP_PASSWORD)

            # Select the mailbox (in readonly mode to avoid marking messages as read)
            mail.select("inbox", readonly=True)

            # Build the search criteria
            search_criteria = []
            if search_email:
                search_criteria.append(f'FROM "{search_email}"')
            if search_subject:
                search_criteria.append(f'SUBJECT "{search_subject}"')

            # Combine the search criteria with AND if both are provided
            if len(search_criteria) > 1:
                search_query = f'({" ".join(search_criteria)})'
            else:
                search_query = search_criteria[0] if search_criteria else 'ALL'

            # Search for messages based on the criteria
            status, messages = mail.search(None, search_query)

            # Convert messages to a list of email IDs
            email_ids = messages[0].split()

            prepare_msg = ""
            attachment = ""

            for email_id in email_ids:
                # Fetch the email by ID
                status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decode the email subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        subject = subject if subject else "No Subject"

                        # Decode the sender's email address
                        from_ = msg.get("From")
                        from_ = from_ if from_ else "Unknown Sender"

                        # Get the date of the email
                        date = msg.get("Date")
                        date = date if date else "Unknown Date"

                        # Check for attachments
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_disposition = part.get("Content-Disposition")
                                if content_disposition and "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename:
                                        filesize = len(part.get_payload(decode=True))
                                        attachment += f"\n{filename} - ({filesize} bytes)\n\n"
                prepare_msg += (
                    f"**UID:** {email_id.decode('utf-8')}\n\n"
                    f"**Date:** {date}\n\n"
                    f"**From:** {from_}\n\n"
                    f"**Subject:** {subject}\n\n"
                    f"**Attachment(s):** {attachment}\n\n"
                )

                help_msg = (
                    f"\n\n**To get email reply with:** QTC:uid[s]\n\n"
                    f"**To get attachment reply with:** DOWNLOAD:uid,filename\n\n"
                )

            prepare_msg += help_msg
            # Logout and close the connection
            mail.logout()
            send_p2p(prepare_msg)
            break  # Exit the loop if successful
        except (imaplib.IMAP4.error, imaplib.IMAP4_SSL.error, ConnectionResetError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                print("All attempts failed. Could not fetch emails.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break


def fetch_emails_by_uids(uids, retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)

            # Login to the account
            mail.login(IMAP_USERNAME, IMAP_PASSWORD)

            # Select the mailbox
            mail.select("inbox")

            # Split the UIDs into a list
            uid_list = uids.split(',')

            prepare_msg = ""
            attachment = ""

            for uid in uid_list:
                # Fetch the email by UID and mark it as read
                status, msg_data = mail.fetch(uid, '(BODY[])')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decode the email subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        subject = subject if subject else "No Subject"

                        # Decode the sender's email address
                        from_ = msg.get("From")
                        from_ = from_ if from_ else "Unknown Sender"

                        # Get the date of the email
                        date = msg.get("Date")
                        date = date if date else "Unknown Date"

                        # Get the body of the email as plaintext
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if "attachment" not in content_disposition:
                                    try:
                                        if content_type == "text/plain":
                                            body += part.get_payload(decode=True).decode()
                                    except UnicodeDecodeError:
                                        body += part.get_payload(decode=True).decode('latin1')
                        else:
                            try:
                                body = msg.get_payload(decode=True).decode()
                            except UnicodeDecodeError:
                                body = msg.get_payload(decode=True).decode('latin1')

                        # Check for attachments
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_disposition = part.get("Content-Disposition")
                                if content_disposition and "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename:
                                        filesize = len(part.get_payload(decode=True))
                                        attachment += f"\n{filename} - ({filesize} bytes)\n\n"
                prepare_msg += (
                    f"**UID:** {uid}\n\n"
                    f"**Date:** {date}\n\n"
                    f"**From:** {from_}\n\n"
                    f"**Subject:** {subject}\n\n"
                    f"**Body:** {body}\n\n"
                    f"**Attachment(s):** {attachment}\n\n"
                )

                help_msg = (
                    f"\n\n**To get email reply with: QTC:uid[s]**\n\n"
                    f"**To get attachment reply with:** DOWNLOAD:uid,filename\n\n"
                )

            prepare_msg += help_msg
            # Logout and close the connection
            mail.logout()
            send_p2p(prepare_msg)
            break  # Exit the loop if successful
        except (imaplib.IMAP4.error, imaplib.IMAP4_SSL.error, ConnectionResetError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                print("All attempts failed. Could not fetch emails.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break


def send_p2p(message):
    # Placeholder function for sending the message
    print("Sending message:", message)


def fetch_unread_emails(retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)

            # Login to the account
            mail.login(IMAP_USERNAME, IMAP_PASSWORD)

            mail.select("inbox", readonly=True)

            # Search for all unread messages
            status, messages = mail.search(None, 'UNSEEN')

            # Convert messages to a list of email IDs
            email_ids = messages[0].split()

            prepare_msg = ""
            attachment = ""

            for email_id in email_ids:
                # Fetch the email by ID
                status, msg_data = mail.fetch(email_id, '(BODY.PEEK[])')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decode the email subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")

                        # Decode the sender's email address
                        from_ = msg.get("From")

                        # Get the date of the email
                        date = msg.get("Date")

                        # Check for attachments
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_disposition = part.get("Content-Disposition")
                                if content_disposition and "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename:
                                        filesize = len(part.get_payload(decode=True))
                                        attachment += f"\n{filename} - ({filesize} bytes)\n\n"
                prepare_msg += (
                    f"**UID:** {email_id.decode('utf-8')}\n\n"
                    f"**Date:** {date}\n\n"
                    f"**From:** {from_}\n\n"
                    f"**Subject:** {subject}\n\n"
                    f"**Attachment(s):** {attachment}\n\n"
                )

            if len(prepare_msg) < 1:
                prepare_msg = (
                    f"**No no e-mails**\n\n"
                )
            else:
                help_msg = (
                    f"\n\n**To get email reply with:** QTC:uid[s]\n\n"
                    f"**To get attachment reply with:** DOWNLOAD:uid,filename\n\n"
            )
                prepare_msg += help_msg

            #            prepare_msg += help_msg

            # Logout and close the connection
            mail.logout()
            send_p2p(prepare_msg)
            break  # Exit the loop if successful
        except (imaplib.IMAP4.error, imaplib.IMAP4_SSL.error, ConnectionResetError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                print("All attempts failed. Could not fetch emails.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break


def send_p2p(message):
    # Placeholder function for sending the message
    print("Sending message:", message)


def handle_message_db_changed():
    print("Message DB has changed!")
    main()


def set_isread(message, status):
    url = "http://localhost:" + config.get('FREEDATA', 'modemport') + "/freedata/messages/" + message

    data = {
        "is_read": status
    }

    # Convert data to JSON format
    payload = json.dumps(data)

    # Set the content type header
    headers = {
        "Content-Type": "application/json"
    }

    # Send POST request
    response = requests.patch(url, data=payload, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        print("POST request successful!")
        print("Response:")
        print(response.json())  # Print the response data
    else:
        print("POST request failed with status code:", response.status_code)


def handle_qtc_query(query):
    # here we can add several trigger words for more function
    if query == "QTC?":
        fetch_unread_emails()
        return "fetch_unread_emails"
    elif query == "QTC:ALL":
        return "TODO: not implemented"
    elif query.startswith("DOWNLOAD:"):
        split_data = query.split(',')
        if len(split_data) > 1:
            uid = split_data[0].replace("DOWNLOAD:", "")
            filename = split_data[1]
            download_attachment(uid, filename)
        return "Downloaded file"
    elif query.startswith("MAILTO:"):
        return query
    elif query.startswith("QTC:SEARCH "):
        split_data = query.split(',')
        if len(split_data) > 1:
            email = split_data[0].replace("QTC:SEARCH ", "")
            subject = split_data[1]
        else:
            email = split_data[0].replace("QTC:SEARCH ", "")
            subject = None
        fetch_filtered_emails(email, subject)
        return "fetch filtered"
    elif query.startswith("QTC:") and query[4:]:
        fetch_emails_by_uids(query[4:])
        return "QTC fetched"
    elif query == "MAILBOX: This is the MBOX your server should parse":
        return "TODO: not implemented"
    else:
        return "Unknown query"


def send_p2p(message):
    url = "http://localhost:" + config.get('FREEDATA', 'modemport') + "/freedata/messages"

    data = {
        "destination": config.get('STATION', 'client'),
        "body": message,
        "type": "raw"
    }

    # Convert data to JSON format
    payload = json.dumps(data)

    # Set the content type header
    headers = {
        "Content-Type": "application/json"
    }

    # Send POST request
    response = requests.post(url, data=payload, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        print("POST request successful!")
        print("Response:")
        print(response.json())  # Print the response data
    else:
        print("POST request failed with status code:", response.status_code)


async def handle_websocket(uri):
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket server")

        while True:
            message = await websocket.recv()
            # TODO remove these print as they now are used for debug
            #print("Received message:", message)

            try:
                data = json.loads(message)
                if data.get("message-db") == "changed":
                    handle_message_db_changed()
                else:
                    print("Unhandled message:", data)
            except json.JSONDecodeError:
                print("Invalid JSON format:", message)
            except Exception as e:
                print("Error processing message:", e)


def send_file_p2p(filename, encoded_string):
    url = "http://localhost:" + config.get('FREEDATA', 'modemport') + "/freedata/messages"

    file = filename

    attachment = {
        'name': file,
        'type': 'raw',
        'data': encoded_string
    }

    #TODO add uid and maybe from e-mail as a comment?
    data = {
        "destination": config.get("STATION", "client"),
        "body": "This is the attachment from your email",
        "attachments": [attachment]
    }

    payload = json.dumps(data)

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 200:
        print("POST request successfully!")
        print("Response:")
        print(response.json())
    else:
        print("POST request failed with status code:", response.status_code)


def download_attachment(uid, attachment_name, retries=3, delay=5):
    for attempt in range(retries):
        try:
            # Connect to the IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)

            # Login to the account
            mail.login(IMAP_USERNAME, IMAP_PASSWORD)

            # Select the mailbox
            mail.select("inbox")

            # Fetch the email by UID
            status, msg_data = mail.fetch(uid, '(BODY.PEEK[])')

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Check for attachments
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_disposition = part.get("Content-Disposition")
                            if content_disposition and "attachment" in content_disposition:
                                filename = part.get_filename()
                                if filename == attachment_name:
                                    # Download the attachment
                                    with open(filename, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    send_file_p2p(filename, part.get_payload(decode=False))
                                    print(f"Attachment {filename} downloaded successfully.")
                                    return

            print(f"Attachment {attachment_name} not found in email with UID {uid}.")

            # Logout and close the connection
            mail.logout()
            break  # Exit the loop if successful
        except (imaplib.IMAP4.error, imaplib.IMAP4_SSL.error, ConnectionResetError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                print("All attempts failed. Could not download attachment.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break


def main():
    # Make a GET request to the API endpoint
    response = requests.get('http://localhost:' + config.get('FREEDATA', 'modemport') + '/freedata/messages')

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse JSON response
        data = response.json()

        # Print fields with content in attachment and is_read = false
        for message in data["messages"]:

            # remove Markdown
            mdown = MarkdownIt(renderer_cls=RendererPlain)

            if mdown.render(message["body"]) and not message["is_read"]:
                parse = mdown.render(message["body"])

                result = handle_qtc_query(parse)

                if result.startswith("MAILTO:"):
                    parts = result.split('|')
                    recipient_email = parts[0].replace("MAILTO:", "")
                    subject = parts[1]
                    body = parts[2]

                    if message["attachments"] and not message["is_read"]:
                        # create a multipart message
                        msg = MIMEMultipart()
                        msg['From'] = sender_email
                        msg['To'] = recipient_email
                        msg['Subject'] = subject

                        if "attachments" in message:
                            attachments = message["attachments"]

                            # This is for encoding
                            msg.attach((MIMEText(body, 'plain')))

                            for attachment in attachments:
                                attachment_field_names = list(attachment.keys())
                                data = attachment["data"]
                                current_directory = os.getcwd()
                                subfolder_attachments = "attachments"
                                subfolder_path = os.path.join(current_directory, subfolder_attachments)
                                attachment = os.path.join(subfolder_path, attachment["name"])
                                decode_base64_to_file(data, attachment)
                                # FIXME should not decode, save , reload and encode the attachement
                                try:
                                    with open(attachment, 'rb') as attachment2:
                                        part = MIMEBase('application', 'octet-stream')
                                        part.set_payload(attachment2.read())
                                        encoders.encode_base64(part)
                                        part.add_header('Content-Disposition', f'attachment; filename={attachment}')
                                        msg.attach(part)
                                except FileNotFoundError:
                                    print(f"Attachemnt not found")
                                    set_isread(message["id"], True)
                    else:

                        print("No attachments - sending plain mail")
                        msg = MIMEText(body, 'plain')
                        msg['From'] = sender_email
                        msg['To'] = recipient_email
                        msg['Subject'] = subject

                        try:
                            with smtplib.SMTP(smtp_server, port) as server:
                                server.starttls()
                                server.login(sender_email, sender_password)
                                server.sendmail(sender_email, recipient_email, msg.as_string())
                                print("Mail sent ok")
                        except Exception as e:
                            print(f"Failed to send email: {e}")
                        # FIXME remove this and only send this after mbox_parse_send() is ok
                        set_isread(message["id"], True)
                set_isread(message["id"], True)


if __name__ == '__main__':
    # Show some basic settings from the config for debug purpose
    exists = os.path.isfile('config_server.ini')

    if exists:
        config = configparser.ConfigParser()
        config.read('config_server.ini')
        configuration = configparser.ConfigParser()
        configuration.read('config_server.ini')

        # Define the IMAP credentials as constants
        IMAP_SERVER = configuration.get('MAIL', 'IMAP_SERVER')
        IMAP_USERNAME = configuration.get('MAIL', 'IMAP_USERNAME')
        IMAP_PASSWORD = configuration.get('MAIL', 'IMAP_PASSWORD')

        # SMTP server details and sender credentials
        smtp_server = configuration.get('MAIL', 'smtp_server')
        port = int(configuration.get('MAIL', 'port'))
        sender_email = configuration.get('MAIL', 'sender_email')
        sender_password = configuration.get('MAIL', 'sender_password')

        mail = imaplib.IMAP4_SSL(IMAP_SERVER)

        # just print these to give some simple information
        print(configuration.get('FREEDATA', 'modemport'))
        print(configuration.get('STATION', 'client'))
        print(configuration.get('MAIL', 'smtp_port'))

    else:
        sys.exit("Missing config")

    main()

    websocket_server_uri = 'ws://localhost:' + config.get('FREEDATA', 'modemport') + '/events'
    asyncio.get_event_loop().run_until_complete(handle_websocket(websocket_server_uri))
