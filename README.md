# FreeDATA_mailbridge

##You really should read this before using.

There are hardly any error handling at the moment.
I'm new to python and this is something I made for my personal need.

See the Wiki for some images of usage.

Minimum requirements:
Your FreeDATA station called [SERVER] should have Internet and be running FreeDATA and "main.py"

The [SERVER] work logic:

    If [SERVER] receive a message an event is triggered.

        If this is a message containing:
            QTC?
            QTC:uid (To get several uids you can use this format  QTC:1,3,4)
            DOWNLOAD:uid,filename
            QTC:SEARCH {from@email.com,subject}
            MAILTO:to@address,subject,body

            parse the message and check the email server. Send the response as a FreeDATA P2P message.

The [CLIENT] work logic:

    From your FreeDATA GUI you can send a P2P message to the [SERVER] callsign-SSID formated like:
            QTC?
                Checks email and reply with a P2P message with all e-mail uid, from, subject and a list of attachments
            QTC:uid (To get several uids you can use this format  QTC:1,3,4)
                Get mail uid #1 or uids #1,3,4 from server and send this as a P2P messages
            QTC:DOWNLOAD uid,filename
                If a messsage has attachments the uid and filename(s) is displayed. Use this to get a P2P messae with the attachment.
            QTC:SEARCH {from@email.com,subject}
                Get email uids containing the from address and/or the subject and send this as a P2P message
                If not searching the from address use this format: QTC:SEARCH ,subject
            MAILTO:to@address,subject,body
