########################################
##### Distributing Exams for jExam #####
########################################

import os
import csv
import base64
import mimetypes
import pkg_resources

from glob import glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_string().encode("utf-8"))
    return {'raw': raw_message.decode("utf-8")}

def create_message_with_attachment(sender, to, subject, message_text, file):
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(message_text)
    message.attach(msg)

    content_type, encoding = mimetypes.guess_type(file)

    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'

    main_type, sub_type = content_type.split('/', 1)

    with open(file, 'rb') as fp:
        msg = MIMEText(fp.read().decode("utf-8"), _subtype=sub_type)

    filename = os.path.basename(file)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(msg)

    raw_message = base64.urlsafe_b64encode(message.as_string().encode("utf-8"))
    return {'raw': raw_message.decode("utf-8")}

def main(args):
    if args.service.lower() == "gmail":
        from . import gmail as client
    
    # auth
    service = client.auth()

    # read student data CSV
    students = csv.DictReader(args.students)

    # read in email template
    if args.template is None:
        email_template_path = pkg_resources.resource_filename(__name__, "email_template.j2")
        with open(email_template_path) as f:
            template = Template(f.read())
    else:
        with open(args.template) as f:
            template = Template(f.read())

    num_exams = len(glob(os.path.join(args.exams_path, "exam_*")))
    notebook_filename = os.path.basename(glob(os.path.join(glob(os.path.join(args.exams_path, "exam_*"))[0]), "*.ipynb")[0])

    for i, student in enumerate(students):
        if (i + 1) % 50 == 0 and not args.quiet:
            print(f"Sending email {i + 1}")

        student_name = student.get("name", None)
        student_email = student["email"]

        email = template.render(
            student_name = student_name
        )

        exam_number = i % num_exams

        message = create_message_with_attachment(
            args.sender,
            student_email,
            args.subject,
            email,
            os.path.join(args.exams_path, f"exam_{exam_number}", notebook_filename)
        )
