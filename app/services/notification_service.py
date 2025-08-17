# services/notification_service.py
import json

from sqlalchemy import select
from app.core.constants import ApplicationStatus, NotificationType
from app.models.application import PermitApplication
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification
from app.services.email_service import send_email_notification
from app.services.sms_service import send_sms_notification
from app.models.user import  Committee, CommitteeMember, DepartmentStaff, User
from typing import Optional, Dict
from sqlalchemy.orm import selectinload

class NotificationService:
    
    STATUS_MESSAGES = {
        ApplicationStatus.DRAFT: {
            "subject": "Application Draft Saved",
            "sms": "Your application draft has been saved. You can continue editing later.",
            "email": "<p>Your application draft has been saved. You can continue editing later.</p>"
        },
        ApplicationStatus.SUBMITTED: {
            "subject": "Application Submitted",
            "sms": "Your application {ref} has been submitted successfully.",
            "email": "<p>Your application <strong>{ref}</strong> has been submitted successfully.</p>",
            "akan": "Wo nhyehyɛe {ref} asɛm no wɔde too gua.",
            "committee_subject": "New Application for Review - {mmda}",
            "committee_message": "New application {ref} submitted to {mmda} requires review."
        },
        ApplicationStatus.UNDER_REVIEW: {
            "subject": "Application Under Review",
            "sms": "Application {ref} is now under review.",
            "email": "<p>Your application <strong>{ref}</strong> is now under review.</p>",
            "akan": "Wɔreyɛ {ref} nhyehyɛe no mu adwuma."
        },
        ApplicationStatus.ADDITIONAL_INFO_REQUESTED: {
            "subject": "Additional Information Required",
            "sms": "Please provide additional information for application {ref}. Check your dashboard.",
            "email": """
                <p>We need more information to process your application <strong>{ref}</strong>.</p>
                <p>Please check your dashboard for details.</p>
            """,
            "akan": "Yɛsrɛ sɛ mfa nkɔm hyɛ {ref} nhyehyɛe no ho."
        },
        ApplicationStatus.APPROVED: {
            "subject": "Application Approved!",
            "sms": "Congratulations! Your application {ref} has been approved.",
            "email": """
                <h3 style="color: #4CAF50;">Congratulations!</h3>
                <p>Your application <strong>{ref}</strong> has been approved.</p>
            """,
            "akan": "Yɛma wo awoda! Wɔagye {ref} nhyehyɛe no tom."
        },
        ApplicationStatus.REJECTED: {
            "subject": "Application Decision",
            "sms": "Your application {ref} has been reviewed. Status: Rejected.",
            "email": """
                <p>Your application <strong>{ref}</strong> has been reviewed.</p>
                <p>Status: <strong style="color: #F44336;">Rejected</strong></p>
            """,
            "akan": "Wɔabua {ref} nhyehyɛe no. Nteɛ: Wɔampene"
        },
        ApplicationStatus.INSPECTION_PENDING: {
            "subject": "Inspection Scheduled",
            "sms": "Inspection scheduled for application {ref}. You'll receive details soon.",
            "email": """
                <p>An inspection has been scheduled for application <strong>{ref}</strong>.</p>
                <p>You'll receive inspection details shortly.</p>
            """,
            "akan": "Wɔayɛ nhwehwɛmu nhyehyɛe ma {ref} nhyehyɛe no."
        },
        ApplicationStatus.INSPECTION_COMPLETED: {
            "subject": "Inspection Completed",
            "sms": "Inspection for application {ref} has been completed. Next steps will follow.",
            "email": """
                <p>The inspection for application <strong>{ref}</strong> has been completed.</p>
                <p>You'll be notified about next steps soon.</p>
            """,
            "akan": "Wɔawie {ref} nhyehyɛe no nhwehwɛmu."
        },
        ApplicationStatus.FOR_APPROVAL_OR_REJECTION: {
            "subject": "Pending Final Decision",
            "sms": "Application {ref} is pending final approval/rejection.",
            "email": """
                <p>Application <strong>{ref}</strong> is now pending final decision.</p>
                <p>You'll be notified once a decision is made.</p>
            """,
            "akan": "{ref} nhyehyɛe no reto mu ma wɔnye pene."
        },
        ApplicationStatus.ISSUED: {
            "subject": "Permit Issued",
            "sms": "Your permit for application {ref} has been issued! Check your dashboard.",
            "email": """
                <h3 style="color: #4CAF50;">Permit Issued!</h3>
                <p>Your permit for application <strong>{ref}</strong> has been issued.</p>
                <p>Please check your dashboard to download the permit.</p>
            """,
            "akan": "Wɔama wo tumi krataa ma {ref} nhyehyɛe no!"
        },
        ApplicationStatus.COMPLETED: {
            "subject": "Process Completed",
            "sms": "The process for application {ref} has been successfully completed.",
            "email": """
                <h3 style="color: #4CAF50;">Process Completed</h3>
                <p>The application process for <strong>{ref}</strong> has been successfully completed.</p>
            """,
            "akan": "Wɔawie {ref} nhyehyɛe no nyinaa."
        },
        ApplicationStatus.CANCELLED: {
            "subject": "Application Cancelled",
            "sms": "Your application {ref} has been cancelled as requested.",
            "email": """
                <p>Your application <strong>{ref}</strong> has been cancelled as requested.</p>
                <p>Contact support if this was unexpected.</p>
            """,
            "akan": "Wɔatow {ref} nhyehyɛe no afi hɔ sɛdeɛ wohwɛe."
        }
    }

    @classmethod
    async def send_application_update(
        cls,
        user: User,
        application_ref: str,
        status: ApplicationStatus,
        additional_info: Optional[str] = None,
        include_akan: bool = True
    ) -> bool:
        """Main method to send status updates"""
        if not user.preferred_verification:
            raise ValueError("User has no preferred verification method set")

        message = cls._prepare_message(application_ref, status, additional_info, include_akan)
        
        if user.preferred_verification == "email":
            return await cls._send_email(user.email, message)
        else:
            return await cls._send_sms(user.phone, message)
    
    @classmethod
    async def send_application_notifications(
    cls,
    db: AsyncSession,
    application: PermitApplication,
    status: ApplicationStatus,
    sender_id: Optional[int] = None,
    additional_info: Optional[str] = None
    ) -> None:
        """Send notifications to applicant and committee members"""
        # Ensure relationships are loaded
        application = await db.execute(
            select(PermitApplication)
            .options(
                selectinload(PermitApplication.mmda),
                selectinload(PermitApplication.applicant),
                selectinload(PermitApplication.committee)
            )
            .where(PermitApplication.id == application.id)
        )
        application = application.scalar_one()

        # Notify applicant
        await cls._notify_applicant(
            db=db,
            application=application,
            status=status,
            sender_id=sender_id,
            additional_info=additional_info
        )

        # Notify committee members if applicable
        if status == ApplicationStatus.SUBMITTED and application.committee_id:
            await cls._notify_committee(
                db=db,
                application=application,
                sender_id=sender_id
            )


    @classmethod
    async def _notify_applicant(
        cls,
        db: AsyncSession,
        application: PermitApplication,
        status: ApplicationStatus,
        sender_id: Optional[int],
        additional_info: Optional[str]
    ) -> None:
        """Send notification to the applicant"""
        mmda_name = application.mmda.name if application.mmda else "the MMDA"
        message = cls._prepare_message(
            ref=application.application_number,
            status=status,
            mmda=mmda_name,
            additional_info=additional_info
        )

        # Store notification in database
        notification = Notification(
            recipient_id=application.applicant.id,
            sender_id=sender_id,
            notification_type=NotificationType.APPLICATION_SUBMITTED,
            title=message["subject"],
            message=message["email"],
            related_application_id=application.id,
            notification_metadata=json.dumps({
                "status": status.value,
                "application_ref": application.application_number
            })
        )
        db.add(notification)
        await db.commit()  # Fix: Use `await` for async commit

        # Send actual notification
        if application.applicant.preferred_verification == "email":
            await send_email_notification(
                email=application.applicant.email,
                subject=message["subject"],
                html_content=message["email"]
            )
        else:
            await send_sms_notification(
                contact=application.applicant.phone,
                message=message["sms"]
            )

    @classmethod
    async def _notify_committee(
    cls,
    db: AsyncSession,
    application: PermitApplication,
    sender_id: Optional[int]
    ) -> None:
        """Notify all committee members about new application"""
        mmda_name = application.mmda.name if application.mmda else "the MMDA"
        message = cls.STATUS_MESSAGES[ApplicationStatus.SUBMITTED]

        # Correct join path: User → DepartmentStaff → CommitteeMember → Committee
        committee_members_result = await db.execute(
            select(User)
            .join(DepartmentStaff, User.id == DepartmentStaff.user_id)
            .join(CommitteeMember, DepartmentStaff.id == CommitteeMember.staff_id)
            .join(Committee, CommitteeMember.committee_id == Committee.id)
            .where(Committee.id == application.committee_id)
        )
        committee_members = committee_members_result.scalars().all()

        for member in committee_members:
            notification = Notification(
                recipient_id=member.id,
                sender_id=sender_id,
                notification_type=NotificationType.REVIEW_REQUESTED,
                title=message["committee_subject"].format(mmda=mmda_name),
                message=message["committee_message"].format(
                    ref=application.application_number,
                    mmda=mmda_name
                ),
                related_application_id=application.id
            )
            db.add(notification)

            if member.preferred_verification == "email":
                await send_email_notification(
                    email=member.email,
                    subject=notification.title,
                    html_content=f"<p>{notification.message}</p>"
                )
            else:
                await send_sms_notification(
                    contact=member.phone,
                    message=notification.message
                )

        await db.commit()

    @classmethod
    def _prepare_message(
        cls,
        ref: str,
        status: ApplicationStatus,
        mmda: str = "",
        additional_info: Optional[str] = None,
        include_akan: bool = True
    ) -> Dict[str, str]:
        """Prepare notification message with MMDA info and Akan translation"""
        base_msg = cls.STATUS_MESSAGES.get(status, {
            "subject": "Application Status Update - {mmda}",
            "sms": "Your application {ref} to {mmda} status has changed to {status}.",
            "email": "<p>Your application <strong>{ref}</strong> to <strong>{mmda}</strong> status has changed to <strong>{status}</strong>.</p>"
        })

        # Format the basic messages
        formatted = {
            "subject": base_msg["subject"].format(mmda=mmda, ref=ref),
            "sms": base_msg["sms"].format(
                ref=ref,
                mmda=mmda,
                status=status.value
            ),
            "email": base_msg["email"].format(
                ref=ref,
                mmda=mmda,
                status=status.value
            )
        }

        # Add Akan translation if available and requested
        if include_akan and "akan" in base_msg:
            akan_message = base_msg["akan"].format(ref=ref)
            
            # Add Akan to SMS (most users receive SMS)
            formatted["sms"] += f"\n\nTwi/Akan: {akan_message}"
            
            # Add Akan to email as well for completeness
            formatted["email"] += f"<br><br><strong>Twi/Akan:</strong> <em>{akan_message}</em>"

        # Add additional information if provided
        if additional_info:
            formatted["sms"] += f"\n\nAdditional Info: {additional_info}"
            formatted["email"] += f"<p><strong>Additional Info:</strong> {additional_info}</p>"

        return formatted

    @classmethod
    async def _send_email(cls, email: str, message: Dict[str, str]) -> bool:
        """Handle email sending"""
        return await send_email_notification(
            email=email,
            subject=f"Digi-Permit: {message['subject']}",
            html_content=message["email"]
        )

    @classmethod
    async def _send_sms(cls, phone: str, message: Dict[str, str]) -> bool:
        """Handle SMS sending"""
        sms_text = f"Digi-Permit: {message['subject']}\n\n{message['sms']}"
        return await send_sms_notification(contact=phone, message=sms_text)