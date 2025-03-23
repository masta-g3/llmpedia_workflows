import smtplib
from email import message
import os


def send_email_alert(tweet_content, arxiv_code):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_EMAIL_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    
    subject = f"New Tweet Alert for arXiv:{arxiv_code}"
    body = f"""
    A new tweet has been posted:

    {tweet_content}

    arXiv link: https://arxiv.org/abs/{arxiv_code}
    Tweet link: https://twitter.com/search?q=from%3ALLMPedia%20{arxiv_code}&src=typed_query&f=live

    """

    msg = message.EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email alert: {str(e)}")


def send_tweet_approval_request(reply_id, selected_tweet, reply_text, response_type):
    """Send an email notification for tweet approval."""
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_EMAIL_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    
    response_type_desc = {
        "a": "academic",
        "b": "funny",
        "c": "common-sense"
    }.get(response_type, "unknown")
    
    subject = f"Tweet Reply Approval Request (ID: {reply_id})"
    
    # Create approval link for Streamlit app
    approval_link = f"https://llmpedia-manager.streamlit.app/?post_id={reply_id}"
    
    body = f"""
    A new tweet reply has been generated and needs your approval:
    
    Original Tweet:
    {selected_tweet}
    
    Generated Reply ({response_type_desc}):
    {reply_text}
    
    To approve or reject this reply, please visit:
    {approval_link}
    
    """

    msg = message.EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            return True
    except Exception as e:
        print(f"Error sending tweet approval request: {str(e)}")
        return False