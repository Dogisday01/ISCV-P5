# Variant Adaptation Map

This document explains how to adapt the universal FastAPI skeleton to any of the 10 P3 variants without changing the security baseline.

## Universal adaptation rules

Keep these parts unchanged unless the assigned variant explicitly requires stronger controls:

- auth flow in `app/api/routes/auth.py`
- password hashing and token logic in `app/core/security.py` and `app/services/auth.py`
- role and object-level authorization pattern in `app/core/authorization.py`
- audit logging pattern in `app/services/audit.py`
- migration workflow through Alembic
- tooling stack: Ruff, mypy, pytest, Bandit, pip-audit

The main customization target is the generic aggregate `WorkflowItem`.
For each variant you will usually adapt:

- `app/models/workflow_item.py`
- `app/schemas/workflow_item.py`
- `app/services/workflow_items.py`
- `app/api/routes/workflow_items.py`
- `docs/foundation-design.md`

## Generic role mapping

The skeleton exposes three roles:

- `user`
- `staff`
- `admin`

Map them as follows:

- `user`: external applicant, customer, patient, citizen, student, subscriber
- `staff`: manager, operator, engineer, doctor, teacher, bank employee
- `admin`: local administrator, security operator, internal auditor

If the variant needs three business roles instead of two, keep `admin` as the technical admin and remap `staff` into the most privileged business actor while introducing one more domain role in `app/models/enums.py`.

## Generic entity mapping

The neutral tables already present are:

- `users`
- `workflow_items`
- `refresh_tokens`
- `audit_logs`

For most variants, keep `users`, `refresh_tokens`, and `audit_logs` intact.
Only rename or specialize `workflow_items`, and add one or two supporting entities when the assigned scenario needs more explicit structure.

## Per-variant map

### 1. Banking: credit approval and monitoring

Use `WorkflowItem` as `CreditApplication`.

Recommended role mapping:

- `user` -> loan applicant
- `staff` -> credit manager
- `admin` -> security or system admin

Recommended minimum entities:

- `users`
- `credit_applications`
- `audit_logs`

Recommended fields for the business object:

- requested amount
- term
- income band
- application status
- staff decision comment

Recommended endpoints:

- create application
- list own applications
- get own application
- approve or reject application
- view current user

Security focus from P3:

- object-level authorization on application access
- protection of personal and financial data
- safe logging of manager actions

Audit events:

- `credit_application.create`
- `credit_application.decision`
- `credit_application.view_sensitive`

### 2. Oil and gas: asset maintenance

Use `WorkflowItem` as `MaintenanceRequest`.

Recommended role mapping:

- `user` -> engineer
- `staff` -> supervisor or dispatcher
- `admin` -> technical admin

Recommended minimum entities:

- `users`
- `maintenance_requests`
- `assets`

Recommended fields:

- asset id
- issue category
- requested date
- work status
- closure notes

Recommended endpoints:

- register maintenance request
- list requests
- get request
- change work status
- optional asset lookup

Security focus:

- server-side check for status updates
- export restrictions
- protection of internal operational data

Audit events:

- `maintenance_request.create`
- `maintenance_request.status_change`
- `maintenance_request.close`

### 3. Retail: order-payment process

Use `WorkflowItem` as `Order`.

Recommended role mapping:

- `user` -> customer
- `staff` -> order manager
- `admin` -> local admin

Recommended minimum entities:

- `users`
- `orders`
- `order_lines`

Recommended fields:

- order total
- currency
- payment status
- delivery address summary
- payment reference

Recommended endpoints:

- create order
- list own orders
- get own order
- confirm payment
- internal order status update

Security focus:

- amount and price validation
- safe payment API integration
- no tokens or card-like values in logs

Audit events:

- `order.create`
- `order.payment_confirm`
- `order.status_change`

### 4. Healthcare: patient treatment and reporting

Use `WorkflowItem` as `PatientCase` or `AppointmentRecord`.

Recommended role mapping:

- `user` -> patient
- `staff` -> doctor
- `admin` -> clinic admin

Recommended minimum entities:

- `users`
- `patient_cases`
- `reports`

Recommended fields:

- appointment datetime
- diagnosis summary
- prescription summary
- report status

Recommended endpoints:

- register patient request
- get patient record
- add medical note or prescription
- generate report
- list own cases or assigned cases

Security focus:

- strict role and object authorization
- audit access to medical data
- no health data leakage in logs or generic error me…1283 chars truncated…unt
- account status

Recommended endpoints:

- register subscriber
- activate tariff
- calculate or view invoice
- view own invoice
- internal account update

Security focus:

- enforce view-only access to own bill
- protect internal billing APIs
- exclude personal data from logs

Audit events:

- `subscriber.register`
- `tariff.activate`
- `invoice.view`

### 7. Logistics: shipment tracking and SLA

Use `WorkflowItem` as `Shipment`.

Recommended role mapping:

- `user` -> customer
- `staff` -> logistics operator
- `admin` -> local admin

Recommended minimum entities:

- `users`
- `shipments`
- `sla_events`

Recommended fields:

- tracking number
- planned delivery datetime
- current status
- SLA breach flag

Recommended endpoints:

- register shipment
- list own shipments
- get shipment
- change shipment status
- optional notify SLA breach

Security focus:

- server-side status authorization
- date/time validation
- safe integration with notification service

Audit events:

- `shipment.create`
- `shipment.status_change`
- `shipment.sla_breach`

### 8. Public sector: citizen service requests

Use `WorkflowItem` as `ServiceRequest`.

Recommended role mapping:

- `user` -> applicant
- `staff` -> public service officer
- `admin` -> internal administrator

Recommended minimum entities:

- `users`
- `service_requests`
- `attachments`

Recommended fields:

- request type
- request status
- decision summary
- attachment metadata

Recommended endpoints:

- submit service request
- list own requests
- get own request
- route or update status
- optional upload attachment metadata

Security focus:

- personal data protection
- file validation and size limits
- separation of citizen and administrative functions

Audit events:

- `service_request.create`
- `service_request.status_change`
- `service_request.attachment_upload`

### 9. Education: enrollment and academic performance

Use `WorkflowItem` as `EnrollmentRequest` or `GradeRecord`.

Recommended role mapping:

- `user` -> student
- `staff` -> teacher or dean office staff
- `admin` -> academic admin

Recommended minimum entities:

- `users`
- `enrollment_requests`
- `grades`

Recommended fields:

- program id
- enrollment status
- course id
- grade value

Recommended endpoints:

- submit enrollment request
- create student record
- assign grade
- view own grades
- internal grade update

Security focus:

- protect grade visibility
- separate teacher and dean office permissions
- audit grade changes

Audit events:

- `enrollment_request.create`
- `student_record.create`
- `grade.change`

### 10. Fintech: digital payments and fraud monitoring

Use `WorkflowItem` as `Payment`.

Recommended role mapping:

- `user` -> customer
- `staff` -> fraud analyst or payment operator
- `admin` -> platform admin

Recommended minimum entities:

- `users`
- `payments`
- `fraud_flags`

Recommended fields:

- amount
- currency
- payment status
- merchant reference
- fraud flag

Recommended endpoints:

- create payment
- confirm payment
- list payment history
- flag suspicious payment
- get payment

Security focus:

- strict amount and currency validation
- access-token protection
- isolation of anti-fraud actions
- safe payment gateway integration

Audit events:

- `payment.create`
- `payment.confirm`
- `payment.flag_suspicious`

## How to rename the generic aggregate

When the variant is assigned, do the renaming in this order:

1. Rename the table and model from `WorkflowItem` to the domain term.
2. Rename route paths from `/workflow-items` to the domain path.
3. Rename schema classes.
4. Rename audit event names.
5. Update Mermaid diagrams and report terminology.

If the variant is simple, you can keep the physical file names and only change class names and API paths.
If you do that, document the mapping explicitly in the report.

## Minimum variant-specific checklist

For the assigned variant, confirm all of these before writing the report:

- the business object name matches the variant
- at least one complete business scenario is implemented
- at least two roles are used in real authorization checks
- object-level access is enforced where required
- logs do not contain passwords, tokens, secrets, or personal data not needed for audit
- at least one `source -> propagation -> sink -> sanitization` chain is described
- Bandit and pip-audit results are included in the report
- the diagrams reflect the final chosen variant, not the generic template

## Cleanup rule before submission

After adapting the project to one assigned variant, delete all unnecessary examples, comments, demo names, and alternative variant references that are not part of that final variant. The submitted codebase and report must look like one focused system, not a multi-variant template.
