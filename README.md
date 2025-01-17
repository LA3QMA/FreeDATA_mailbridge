# FreeDATA_mailbridge

##You really should read this before using.

There are hardly any error handling at the moment.
I'm new to python and this is something i made for my personal need.

Minimum requirements:
Your FreeDATA station called [SERVER] should have Internet and be running FreeDATA and "main.py"

The [SERVER] work logic:

    If [SERVER] receive a message an event is triggered.

        If this is a message containing:
            QTC?
                Checks email and reply with a P2P message with all e-mail uid, from and subject
            QTC:uid (To get several uids you can use this format  QTC:1,3,4)
                Get mail uid #1 or uids #1,3,4 from server and send this as a P2P messages
            QTC:SEARCH {from@email.com,subject}
                Get emails containing the from address and/or the subject and send this as a P2P message
            MAILTO:to@address,subject,body
                Parse message and send this as email. If any attachments this is also included.

The [CLIENT] work logic:

    From your FreeDATA GUI you can send a P2P message to the [SERVER] callsign-SSID formated like:
        MAILTO:to@address,subject,body
        ps: before transmitting this you can attach files from FreeDATA GUI
        QTC?
        QTC:uid[,uid,uid...]

        FreeDATA is then transmitting this to the [SERVER] via P2P
