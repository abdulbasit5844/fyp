COMSATS University, Islamabad Pakistan
A Vision Based Driver Monitoring and Safety Assistance
System
By
Muneeb Khan CIIT/SP23-BAI-039/ISB
Abdul Basit CIIT/FA22-BAI-001/ISB
Supervisor
Dr Inayat-ur-Rehman
Co-Supervisor
Dr. Sumeera Batool Dr. Muhammad Dilshad Sabir
Bachelor of Science in Artificial Intelligence (2022-2027)
The candidates confirms that the work submitted is their own and appropriate
credit has been given where reference has been made to the work of others.

SRS – Vision Based Driver Monitoring and Safety Assistance System
DECLARATION
We hereby declare that this software requirements specification, neither whole nor as a part, has been
copied out from any source. It is further declared that we have developed this SRS document and the
accompanying project entirely on the basis of our personal efforts. If any part of this document is
proved to be copied out from any source or found to be a reproduction of some other work, we will
stand by the consequences. No portion of the work presented has been submitted in any application
for any other degree or qualification at this or any other university or institute of learning.
Abdul Basit Muneeb Khan
________________________ ________________________
COMSATS University Islamabad | BS Artificial Intelligence | Page 2

SRS – Vision Based Driver Monitoring and Safety Assistance System
Abstract
Road accidents caused by driver fatigue, drowsiness, and loss of attentiveness remain a major global
safety concern, particularly in regions where advanced in-vehicle safety technologies are not widely
accessible. Modern high-end vehicles increasingly incorporate intelligent driver monitoring features;
however, such solutions are prohibitively expensive and unavailable to the vast majority of vehicle
owners. This project targets three core challenges: delayed driver reaction times, the absence of real-
time behavioral monitoring, and the lack of automated emergency escalation mechanisms in
conventional vehicles. A significant gap exists in providing low-latency, privacy-preserving, and
affordable driver safety solutions that operate without dependency on continuous cloud connectivity.
The proposed system detects driver emotions, drowsiness levels, and abnormal behavioral patterns
using computer vision models deployed locally on a Raspberry Pi edge device, ensuring real-time
responsiveness and data privacy. Upon detection of unsafe conditions, the system generates immediate
audio and visual alerts; if the driver fails to acknowledge within a configurable time window, an
emergency escalation mechanism activates, transmitting the vehicle’s GPS location to up to five pre-
selected emergency contacts via a companion mobile application. Additional capabilities include
event-based video recording, unauthorized occupant detection, and key-left-inside alerts. The
significance of this project lies in making intelligent driver safety assistance genuinely affordable and
accessible to everyday vehicle owners through embedded AI and computer vision — bridging the gap
between expensive factory-fitted systems and the needs of the general public.
COMSATS University Islamabad | BS Artificial Intelligence | Page 3

SRS – Vision Based Driver Monitoring and Safety Assistance System
Acknowledgement
All praise is to Almighty Allah who bestowed upon us a portion of His boundless knowledge, by virtue
of which we were able to accomplish this challenging undertaking.
We are deeply indebted to our project supervisor Dr Inayat-ur-Rehman and our Co-Supervisor Dr.
Samera Batool and Dr. Muhammad Dilshad Sabir. Without their personal supervision, constructive
advice, and invaluable guidance, the completion of this project would have been doubtful. We are
grateful to them for their continuous encouragement and support throughout this work.
We are also thankful to the Final Year Project Committee at COMSATS University Islamabad for
providing a structured framework for project evaluation and feedback. Finally, we owe our deepest
gratitude to our parents and families who have been a constant source of motivation and have
supported us with the values of honesty and hard work.
Abdul Basit Muneeb Khan
________________________ ________________________
COMSATS University Islamabad | BS Artificial Intelligence | Page 4

SRS – Vision Based Driver Monitoring and Safety Assistance System
Abbreviations
ABBREVIATION FULL FORM
SRS Software Requirements Specification
AI Artificial Intelligence
CV Computer Vision
FYP Final Year Project
GPS Global Positioning System
IOT Internet of Things
MQTT Message Queuing Telemetry Transport
ONNX Open Neural Network Exchange
API Application Programming Interface
UI User Interface
UX User Experience
JWT JSON Web Token
NFR Non-Functional Requirement
FR Functional Requirement
DMS Driver Monitoring System
RPI Raspberry Pi
COMSATS University Islamabad | BS Artificial Intelligence | Page 5

SRS – Vision Based Driver Monitoring and Safety Assistance System
Table of Contents
Declaration .......................................................................................................................... 2
Abstract ............................................................................................................................... 3
Acknowledgement .............................................................................................................. 4
Abbreviations ...................................................................................................................... 5
Chapter 1: Introduction and Problem Definition .............................................................. 8
1.1 Overview of the Project ............................................................................................ 8
1.2 Vision Statement ...................................................................................................... 8
1.3 Problem Statement ................................................................................................... 8
1.4 Problem Solution ...................................................................................................... 9
1.5 Objectives of the Proposed System ....................................................................... 9
1.6 Scope......................................................................................................................... 9
1.6.1 Limitations / Constraints ................................................................................. 10
1.7 Modules ................................................................................................................... 10
Module 1: Driver Monitoring and Analysis .............................................................. 10
Module 2: Edge AI Processing Unit ......................................................................... 10
Module 3: Alert and Emergency Escalation System (Edge) ................................... 11
Module 4: Vehicle Safety Enhancements ................................................................ 11
Module 5: User Authentication and Authorization (Mobile App) ........................... 11
Module 6: Alert Management and Emergency Escalation (Mobile App) ............... 11
Module 7: Monitoring, Logs, and Configuration (Mobile App) ............................... 11
Module 8: Web-Based Dashboard ............................................................................ 12
1.8 Related System Analysis / Literature Review ...................................................... 12
1.9 Tools and Technologies ........................................................................................ 13
1.10 Project Contribution ............................................................................................. 14
1.11 Relevance to Course Modules ............................................................................ 14
Chapter 2: Requirement Analysis .................................................................................... 16
2.1 User Classes and Characteristics ......................................................................... 16
2.2 Operating Environment .......................................................................................... 16
2.3 Design and Implementation Constraints .............................................................. 16
2.4 Use Case Diagram .................................................................................................. 17
Module 1 – Driver Monitoring and Analysis ................................................................ 17
Modules 3 & 6 – Alert Management and Emergency Escalation ............................... 18
COMSATS University Islamabad | BS Artificial Intelligence | Page 6

SRS – Vision Based Driver Monitoring and Safety Assistance System
Modules 5 & 7 – Mobile Application User Interactions .............................................. 19
Module 8 – Web-Based Administrative Dashboard .................................................... 20
2.5 Requirement Identifying Technique...................................................................... 22
2.6 Functional Requirements ...................................................................................... 22
2.7 Non-Functional Requirements .............................................................................. 25
2.8 External Interface Requirements .......................................................................... 26
Chapter 3: Design and Architecture ................................................................................ 28
3.1 System Architecture Overview .............................................................................. 28
3.2 Technologies and Services by Component ......................................................... 28
3.3 Architecture Style / Pattern ................................................................................... 29
3.4 Design Models ........................................................................................................ 29
3.5 Data Design ............................................................................................................. 30
Chapter 4: Implementation ............................................................................................... 31
4.1 Project Methodology and Algorithms ................................................................... 31
4.2 Training Results and Model Evaluation (Mandatory for AI/ML Projects) ........... 32
4.3 Security Techniques .............................................................................................. 32
4.4 External APIs / SDKs .............................................................................................. 32
4.5 User Interface ......................................................................................................... 32
4.6 Deployment ............................................................................................................. 39
Chapter 5: Testing and Evaluation .................................................................................. 40
5.1 Unit Testing ............................................................................................................. 40
5.2 Functional Testing.................................................................................................. 40
5.3 Business Rules Testing ......................................................................................... 41
5.4 Integration Testing ................................................................................................. 41
Chapter 6: Conclusion and Future Work ........................................................................ 42
6.1 Conclusion .............................................................................................................. 42
6.2 Future Work ............................................................................................................ 42
Chapter 7: References ...................................................................................................... 43
COMSATS University Islamabad | BS Artificial Intelligence | Page 7

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 1: Introduction and Problem Definition
This chapter provides a comprehensive overview of the Vision Based Driver Monitoring and Safety
Assistance System. It covers the project background, vision statement, problem definition, proposed
solution, objectives, scope, system modules, related system analysis, tools and technologies, project
contribution, and relevance to academic course modules.
1.1 Overview of the Project
The Vision Based Driver Monitoring and Safety Assistance System is an intelligent, embedded AI-
based solution designed to enhance road safety by continuously monitoring driver behavior using a
camera and deploying computer vision models on a Raspberry Pi edge device. The system operates in
real time without dependence on cloud infrastructure, making it suitable for deployment in any vehicle
regardless of connectivity. It detects driver drowsiness, emotional states, and attentiveness levels,
generating immediate alerts when unsafe conditions are identified. If the driver remains unresponsive
to alerts, an emergency escalation mechanism transmits the vehicle’s GPS location to pre-selected
emergency contacts through a companion mobile application. The system additionally provides event-
based video recording, unauthorized occupant detection, and key-left-inside alerts. A web-based
administration dashboard complements the mobile application by providing analytics, logs, and
system management capabilities. The project bridges a critical gap between expensive factory-fitted
driver monitoring solutions available only in premium vehicles and the safety needs of the broader
driving population.
1.2 Vision Statement
For everyday vehicle owners who require intelligent safety assistance, the Vision Based Driver
Monitoring and Safety Assistance System is an embedded AI-based solution that monitors driver
behavior, detects unsafe conditions, and escalates emergencies in real time. Unlike existing high-end
automotive safety systems such as Tesla’s Driver Monitoring or Mercedes-Benz Driver Attention
Assist, which are proprietary, expensive, and restricted to premium vehicles, our product provides
low-latency decision-making, privacy-preserving on-device operation, and affordability using edge
computing and computer vision technologies making advanced driver safety accessible to all vehicle
owners.
1.3 Problem Statement
Road accidents due to driver fatigue, drowsiness, and emotional instability pose a serious and
persistent threat to human life and property worldwide. Many drivers remain unaware of their own
deteriorating mental or physical state during long or stressful driving sessions. Existing vehicles,
particularly low- and mid-range models, lack intelligent systems capable of monitoring driver behavior
in real time. Traditional safety mechanisms rely heavily on manual intervention and do not provide
proactive alerts or automated emergency escalation. Cloud-based monitoring solutions introduce
latency, dependency on internet connectivity, and significant privacy risks associated with continuous
data transmission. Furthermore, vehicle theft and unauthorized access remain common issues,
especially in regions without advanced car security infrastructure. Drivers also lack systems that can
automatically notify trusted emergency contacts during critical situations. These challenges
COMSATS University Islamabad | BS Artificial Intelligence | Page 8

SRS – Vision Based Driver Monitoring and Safety Assistance System
collectively highlight the urgent need for a low-cost, real-time, and intelligent driver monitoring
solution that can operate independently and be retrofitted into any vehicle.
1.4 Problem Solution
The proposed system addresses these challenges through a camera-based vision solution that
continuously observes the driver and vehicle interior. Optimized computer vision models are deployed
directly on a Raspberry Pi to perform real-time inference with minimal latency, eliminating cloud
dependency for core operations. The system detects driver drowsiness, emotional distress, and
inattentive behavior, generating immediate audio and visual alerts upon detection of unsafe conditions.
A configurable acknowledgment mechanism allows the driver to dismiss alerts; if no response is
received within a predefined threshold, the emergency escalation module activates and transmits GPS
location data to up to five emergency contacts through a mobile application. Secondary safety features
include event-based video recording triggered by safety events, unauthorized occupant detection using
face recognition, and key-left-inside alerts. An administrative web dashboard provides fleet operators
and owners with monitoring, log access, and configuration capabilities. The solution is designed as an
assistive advisory tool rather than a replacement for existing vehicle safety mechanisms, with the
primary goal of making advanced driver safety affordable and accessible at scale.
1.5 Objectives of the Proposed System
• BO-1: Detect driver drowsiness and emotional states in real time using vision-based AI
models achieving at least 85% detection accuracy under controlled in-vehicle lighting
conditions.
• BO-2: Ensure low-latency and real-time decision-making using edge computing on
Raspberry Pi, with inference response times under 200 milliseconds per frame.
• BO-3: Generate immediate visual and audio alerts to warn the driver upon detection of
unsafe conditions with fewer than 2 seconds of delay from event detection.
• BO-4: Escalate emergencies by automatically transmitting GPS location to 3 to 5 selected
emergency contacts via the mobile application if driver alerts are not acknowledged within a
configurable time window.
• BO-5: Record and store event-based video footage for critical safety incidents, ensuring
efficient storage usage through trigger-based recording.
• BO-6: Detect unauthorized occupants as a secondary vehicle safety feature using facial
recognition and detection.
• BO-7: Provide a mobile application for real-time alert reception, system monitoring,
emergency contact management, and user configuration.
1.6 Scope
The scope of this project includes the development of a real-time driver monitoring and safety
assistance system using a camera and embedded artificial intelligence deployed on a Raspberry Pi.
The system will continuously analyze live video streams to detect driver drowsiness, emotional states,
and inattentive behavior in real time. All critical inference and decision-making processes will be
executed locally on the edge device to ensure minimal latency and preserve user privacy. The system
will generate audio and visual alerts when unsafe driver states are detected, and a driver
COMSATS University Islamabad | BS Artificial Intelligence | Page 9

SRS – Vision Based Driver Monitoring and Safety Assistance System
acknowledgment mechanism will allow dismissal of alerts within a configurable window. Event-based
video recording will capture and store footage only during triggered safety incidents, optimizing
storage consumption. A mobile application will be developed to allow vehicle owners to receive real-
time safety alerts, view event logs, manage emergency contacts, and configure system parameters. In
the event that safety alerts are not acknowledged by the driver, the system will automatically transmit
the vehicle’s GPS location to up to five pre-selected emergency contacts through the mobile
application. Secondary safety features will include unauthorized occupant detection using face
recognition and a key-left-inside alert mechanism. A web-based administrative dashboard will provide
system analytics, real-time driver event monitoring, and administrative control. Cloud dependency
will be avoided for all core detection and escalation functionalities. The project is scoped to prototype-
level deployment for experimental validation and academic evaluation purposes, and is intended as an
assistive advisory safety tool rather than a certified medical or legal safety device.
1.6.1 Limitations / Constraints
• LI-1: System detection performance depends significantly on interior vehicle lighting
conditions; low-light or high-glare environments may reduce accuracy.
• LI-2: Face recognition and drowsiness detection accuracy may vary due to occlusions such as
sunglasses, face masks, or non-frontal head orientations.
• LI-3: The computational resources of the Raspberry Pi limit the complexity and number of
AI models that can run concurrently in real time.
• LI-4: The system is intended as an assistive and advisory safety tool and is not a certified
medical device, legal evidence system, or replacement for professional safety assessments.
• LI-5: Emergency escalation via GPS requires the mobile application to be active and the
device to have internet connectivity at the time of escalation.
• LI-6: The prototype is validated in controlled experimental environments and is not yet
intended for mass-market commercial deployment.
1.7 Modules
The system is organized into eight functional modules covering the edge device, mobile application,
and web dashboard.
Module 1: Driver Monitoring and Analysis
• FE-1: Live camera stream processing and frame capture from the in-vehicle camera.
• FE-2: Real-time driver drowsiness detection using eye aspect ratio and facial landmark
analysis.
• FE-3: Driver emotion and facial state analysis using deep learning classification models.
• FE-4: Head pose estimation to detect driver inattentiveness or distraction.
Module 2: Edge AI Processing Unit
• FE-1: Deployment of optimized and quantized AI models on Raspberry Pi for on-device
inference.
• FE-2: Real-time multi-model inference pipeline management and decision logic execution.
COMSATS University Islamabad | BS Artificial Intelligence | Page 10

SRS – Vision Based Driver Monitoring and Safety Assistance System
• FE-3: Latency optimization through model compression, ONNX conversion, and hardware
acceleration where available.
• FE-4: Resource management to ensure concurrent execution of monitoring, recording, and
alert modules.
Module 3: Alert and Emergency Escalation System (Edge)
• FE-1: Generation of audio and visual alerts upon detection of unsafe driver states.
• FE-2: Driver acknowledgment detection mechanism with configurable response time
window.
• FE-3: Emergency escalation logic that activates GPS location transmission when alerts are
not acknowledged.
• FE-4: Integration testing and calibration of alert thresholds to minimize false positives.
Module 4: Vehicle Safety Enhancements
• FE-1: Unauthorized occupant detection using facial recognition to identify unknown persons
in the vehicle.
• FE-2: Key-left-inside detection logic using sensor input or camera-based object detection.
• FE-3: Event-based video recording triggered by critical safety events, stored locally on the
device.
• FE-4: Accuracy testing and validation of detection thresholds for vehicle safety features.
Module 5: User Authentication and Authorization (Mobile App)
• FE-1: User registration and secure login functionality for vehicle owners within the mobile
application.
• FE-2: Authentication of the vehicle owner and verification of identity for sensitive
operations.
• FE-3: Management of authorized users and their access levels to vehicle safety features and
configurations.
• FE-4: Secure session handling, JWT-based token management, and access control
enforcement.
Module 6: Alert Management and Emergency Escalation (Mobile App)
• FE-1: Real-time reception of safety alerts transmitted from the Raspberry Pi edge device to
the mobile application.
• FE-2: Driver alert acknowledgment mechanism accessible through the mobile application
interface.
• FE-3: Automatic emergency escalation workflow triggered when driver acknowledgment is
not received.
• FE-4: Transmission of GPS location data to 3 to 5 user-selected emergency contacts via push
notification or SMS.
Module 7: Monitoring, Logs, and Configuration (Mobile App)
COMSATS University Islamabad | BS Artificial Intelligence | Page 11

SRS – Vision Based Driver Monitoring and Safety Assistance System
• FE-1: Display of safety event logs, alert history, and system status notifications within the
mobile application.
• FE-2: Access to event-based recorded video clips from the edge device storage.
• FE-3: Management of emergency contacts, alert thresholds, and escalation time windows.
• FE-4: System configuration and user preference settings including sensitivity adjustments.
Module 8: Web-Based Dashboard
• FE-1: Administrative dashboard UI for real-time monitoring of driver states and vehicle
safety events.
• FE-2: Backend API integration and database connectivity for centralized data management.
• FE-3: Data visualization through interactive charts and graphs displaying alert history, event
logs, and system analytics.
• FE-4: Administration of system settings, user roles, and secure access control for fleet or
institutional deployments.
1.8 Related System Analysis / Literature Review
1.8.1 Literature Review
Prior research in driver monitoring and fatigue detection has established strong foundations for the
techniques employed in this project. Significant work has been conducted on eye-based drowsiness
indicators; studies analyzing Eye Aspect Ratio (EAR) using Dlib facial landmarks have demonstrated
reliable drowsiness detection under controlled conditions, with limitations in low-light environments.
Research by Viola and Jones, extended through MediaPipe’s face mesh pipeline, has enabled efficient
real-time facial landmark detection suitable for edge deployment. Emotion recognition using
convolutional neural networks has been explored extensively, with models trained on datasets such as
FER-2013 and AffectNet achieving competitive accuracy for the seven basic emotion categories.
Edge AI deployment for automotive applications has been explored in several academic and industry
contexts. Studies demonstrate that lightweight architectures such as MobileNetV2 and EfficientNet-
Lite, when quantized to INT8 precision, achieve acceptable inference speeds on ARM-based devices
like the Raspberry Pi 4 with acceptable accuracy trade-offs. Research on ONNX Runtime and
TensorFlow Lite confirms their suitability for constrained hardware deployment.
Existing commercial systems such as Tesla’s Driver Monitoring System and Mobileye’s driver
attention solutions are well-documented in literature but share the common limitation of being tightly
integrated with proprietary vehicle hardware and unavailable as aftermarket solutions. Research gaps
identified across the literature include the lack of integrated emergency GPS escalation with
contactless acknowledgment, privacy-preserving edge-only operation, and affordable multi-feature
driver safety platforms targeting developing markets. This project directly addresses these identified
gaps.
1.8.2 Related System Analysis
Application Name Weakness Proposed Project Solution
Tesla Driver Limited to high-end vehicles; Provides a low-cost vision-based
Monitoring System significantly increases vehicle driver monitoring solution
COMSATS University Islamabad | BS Artificial Intelligence | Page 12

SRS – Vision Based Driver Monitoring and Safety Assistance System
cost making it inaccessible to the deployable in any vehicle using
general public. edge AI on affordable hardware.
Mercedes-Benz Driver Available only in premium Uses a standard USB or CSI
Attention Assist models; relies on proprietary camera with embedded AI to offer
hardware and sensors with no comparable safety assistance
aftermarket availability. without specialized vehicle
integration.
Smartphone-Based Unreliable camera positioning, Utilizes a fixed in-vehicle camera
Fatigue Detection Apps high false positive rates, and with optimized computer vision
inconsistent performance due to models achieving superior
varying phone placement during accuracy and consistency.
driving.
Cloud-Based Driver Introduces significant latency, All critical processing is
Monitoring Systems depends on continuous internet performed on-device using the
connectivity, and raises user Raspberry Pi, ensuring real-time
privacy concerns due to performance and data privacy
continuous data streaming. preservation.
Traditional Vehicle Focus primarily on alarms and Integrates vision-based
Security Systems physical locks without any unauthorized occupant detection,
intelligent occupant behavioral key-left-inside alerts, and GPS
analysis or emergency emergency escalation as an
communication capabilities. assistive safety layer.
Table 1.1: Related System Analysis with Proposed Project Solution
1.9 Tools and Technologies
Module Technology Tools / Libraries / Hardware / Platform
Frameworks
Module 1: Driver Python, Computer OpenCV, Dlib, Raspberry Pi 4
Monitoring and Vision, AI MediaPipe, TensorFlow (4GB/8GB) with
Analysis Lite / ONNX, NumPy Camera Module v2
Module 2: Edge AI Edge Computing, ONNX Runtime, Raspberry Pi 4
Processing Unit AI Optimization TensorFlow Lite, (4GB/8GB) or Jetson
OpenVINO (optional), Nano
Python
Module 3: Alert and Real-time alerting, Python, Pygame / Raspberry Pi, LEDs /
Emergency IoT playsound, MQTT / Buzzer for visual/audio
Escalation (Edge) Firebase Push alerts
Notifications
Module 4: Vehicle Object Detection, OpenCV, Raspberry Pi Camera,
Safety Enhancements Event-triggered face_recognition, Motion Sensors
Recording Python (optional)
COMSATS University Islamabad | BS Artificial Intelligence | Page 13

SRS – Vision Based Driver Monitoring and Safety Assistance System
Module 5: User Web JWT / OAuth2, Firebase Mobile device (Android
Authentication Authentication, Authentication / iOS), Server
(Mobile) Session
Management
Module 6: Alert Real-time Data Python, MQTT / Mobile device,
Management Streaming, GPS WebSockets, Google Raspberry Pi, GPS
(Mobile) Integration Maps API / Module
OpenStreetMap
Module 7: Logging, Flutter / React Native, Mobile device, Local
Monitoring, Logs, Configuration Python Logging, Server / AWS
Configuration Management PostgreSQL / Firebase
(Mobile)
Module 8: Web- Web JavaScript, React.js, Local Server / AWS /
Based Dashboard Development, Node.js, PostgreSQL Heroku
Data Visualization
Table 1.2: Tools and Technologies for Proposed Project
1.10 Project Contribution
The Vision Based Driver Monitoring and Safety Assistance System introduces several technical and
conceptual contributions compared to existing commercial and academic solutions:
• Affordable Edge-Based Driver Monitoring: Deploys optimized AI models on a Raspberry Pi
instead of proprietary automotive hardware, making intelligent driver monitoring accessible
at a fraction of the cost of commercial systems.
• Integrated Emergency Escalation with GPS: Combines in-vehicle alert generation with
automated GPS location transmission to emergency contacts — a feature absent in most
academic prototypes and restricted to luxury vehicles in commercial systems.
• Privacy-Preserving On-Device Inference: Performs all critical AI inference locally without
transmitting sensitive video or biometric data to the cloud, directly addressing the privacy
limitations of cloud-based monitoring solutions.
• Multi-Feature Safety Platform: Consolidates drowsiness detection, emotion recognition,
unauthorized occupant detection, key-left-inside alerts, and event-based video recording into
a single retrofittable system — a level of feature integration not found in existing aftermarket
solutions.
• Acknowledgment-Based Alert Management: Implements a driver acknowledgment
mechanism that distinguishes between drivers who respond to alerts and those who are
incapacitated, triggering appropriate escalation only when warranted.
• Dual-Interface Monitoring: Provides both a mobile application for vehicle owners and a web-
based administrative dashboard, enabling individual and fleet-level safety monitoring with
role-based access control.
1.11 Relevance to Course Modules
• Computer Vision (CV): Applied as the core technology for face detection, drowsiness
detection, emotion recognition, unauthorized occupant detection, and event-based video
analysis from live camera streams.
COMSATS University Islamabad | BS Artificial Intelligence | Page 14

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Artificial Neural Networks (ANN): Used to implement deep learning classification models
for real-time detection of driver drowsiness states, facial expressions, and other behavioral
patterns derived from video input.
• Machine Learning (ML): Enabled training and evaluation of predictive models for driver
state classification and anomaly detection, including selection of appropriate lightweight
architectures for edge deployment.
• Operating Systems (OS): Applied for process management, multitasking, and resource
allocation on the Raspberry Pi, enabling concurrent execution of camera capture, AI
inference, alert generation, and communication threads.
• Computer Networks (CN): Applied for TCP/IP and MQTT-based communication between
the edge device and the mobile application, including wireless data transmission and IoT
protocol design for real-time alert delivery.
• Database Systems: Applied in designing structured databases for driver event logs, alert
histories, emergency contacts, user profiles, and system configurations using PostgreSQL
and Firebase.
• Web Technologies: Used for developing the interactive administrative dashboard using
React.js and Node.js, with RESTful API design for backend data management.
• Object-Oriented Programming (OOP): Applied for designing modular and maintainable code
classes for the driver monitoring pipeline, alert system, user authentication, and dashboard
components.
• Design and Analysis of Algorithms (DAA): Applied for optimizing real-time inference
scheduling, alert priority management, and multi-model pipeline execution on resource-
constrained hardware.
• Software Engineering: SDLC phases, requirement elicitation, SRS documentation, modular
design, and testing methodology were applied throughout the project development lifecycle.
COMSATS University Islamabad | BS Artificial Intelligence | Page 15

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 2: Requirement Analysis
This chapter presents a detailed requirements analysis of the Vision Based Driver Monitoring and
Safety Assistance System. It identifies user classes, describes the operating environment and design
constraints, documents functional requirements derived from system interactions, and specifies non-
functional quality attributes and external interface requirements.
2.1 User Classes and Characteristics
User Class Description Characteristics
Vehicle Owner / Primary user who operates the Non-technical; requires minimal
Driver vehicle and interacts with the mobile interface complexity; uses mobile
application for configuration, alert app; receives real-time alerts.
acknowledgment, and monitoring.
Emergency Person(s) designated to receive GPS No active system interaction;
Contact location and emergency alerts when receives push notifications or SMS
the driver is unresponsive to system passively.
alerts.
System Technical user responsible for Technical background; uses web
Administrator managing the web dashboard, user dashboard; manages system settings
accounts, system configurations, and and user roles.
analytics.
Supervisor / Fleet Optional institutional user who Semi-technical; requires read access
Manager monitors multiple vehicle safety logs to monitoring dashboard and
and event reports through the web analytics; no configuration rights.
dashboard for fleet-level oversight.
Table 2.1: User Classes and Characteristics
2.2 Operating Environment
• OE-1: The edge device component shall operate on a Raspberry Pi 4 (4GB or 8GB RAM)
running Raspberry Pi OS (64-bit) or Ubuntu 22.04 LTS, connected to a compatible camera
module.
• OE-2: The mobile application shall operate on Android devices running Android 10 (API
Level 29) or higher, with access to internet connectivity for push notifications and GPS
escalation features.
• OE-3: The web-based administrative dashboard shall operate correctly on Google Chrome
(v100+), Mozilla Firefox (v100+), and Microsoft Edge (v100+) with a minimum screen
resolution of 1366x768.
• OE-4: The system shall operate within a vehicle interior environment at temperatures
between 0°C and 55°C and in ambient lighting conditions ranging from 50 lux (dim interior)
to standard interior illumination.
• OE-5: The backend server components shall be hosted on a local server or cloud platform
such as AWS or Heroku, accessible over HTTPS.
2.3 Design and Implementation Constraints
COMSATS University Islamabad | BS Artificial Intelligence | Page 16

SRS – Vision Based Driver Monitoring and Safety Assistance System
• CON-1: All critical driver monitoring inference must be performed on-device on the
Raspberry Pi without requiring internet connectivity for core functionality.
• CON-2: AI models deployed on the edge device must be optimized for ARM architecture
using TensorFlow Lite or ONNX Runtime and must achieve real-time inference at a
minimum of 15 frames per second.
• CON-3: The mobile application must be developed using Flutter or React Native to support
cross-platform deployment.
• CON-4: Communication between the edge device and mobile application must use MQTT or
WebSocket protocol for low-latency real-time data transfer.
• CON-5: All user authentication must be implemented using JWT or OAuth 2.0 standards
with HTTPS-enforced communication.
• CON-6: Event-based video recording must be stored locally on the Raspberry Pi and made
accessible for retrieval through the mobile application.
• CON-7: The system is constrained to prototype-level deployment for experimental validation
within the academic project timeline.
2.4 Use Case Diagram
The following section describes the identified use cases for each user class interacting with the system.
Actor Use Cases Description
Vehicle Owner / Login, Configure Alert Thresholds, Primary interaction through mobile
Driver View Event Logs, Manage application for configuration,
Emergency Contacts, Acknowledge monitoring, and alert management.
Alerts, View Recorded Videos
Raspberry Pi (Edge Capture Video, Detect Drowsiness, Automated system actor performing
Device) Detect Emotion, Generate Alert, continuous monitoring and safety
Record Event Video, Transmit GPS decision-making.
Location
Emergency Contact Receive Emergency Notification Passive recipient of emergency
with GPS Location escalation alerts.
System Login to Dashboard, Manage Users, Administrative interaction through
Administrator View Analytics, Configure System web dashboard for system
Settings oversight.
Table 2.2: Use Case Summary by Actor
Module 1 – Driver Monitoring and Analysis
This diagram focuses on the camera-based driver monitoring pipeline. The primary actor is the
Raspberry Pi edge device, which continuously interacts with the camera to process frames. The Alert
Manager is shown as a secondary actor receiving the results of detection use cases.
COMSATS University Islamabad | BS Artificial Intelligence | Page 17

SRS – Vision Based Driver Monitoring and Safety Assistance System
Figure 1.2 – Use Case Diagram: Module 1 – Driver Monitoring and Analysis
The diagram illustrates three parallel detection use cases — drowsiness detection, emotion
classification, and head pose estimation — each including a temporal consistency filter and frame
optimization step. This reflects the requirement that no single-frame event may trigger an alert;
sustained detection over a configurable duration is required.
Modules 3 & 6 – Alert Management and Emergency Escalation
This diagram captures the full alert lifecycle from event detection on the edge device through
acknowledgment or escalation. Three actors interact: the Driver (who receives and may acknowledge
alerts), the Emergency Contacts (who passively receive escalation notifications), and the Mobile
Application (which relays GPS and push notifications).
COMSATS University Islamabad | BS Artificial Intelligence | Page 18

SRS – Vision Based Driver Monitoring and Safety Assistance System
Figure 1.3 – Use Case Diagram: Alert Management and Emergency Escalation (Modules 3 & 6)
Notable design decisions reflected in this diagram:
• The Transmit GPS Location use case is connected to both Emergency Contacts and the
Mobile Application actor, representing the two-step relay: the mobile application receives
GPS data from the edge device and forwards it to contacts via FCM push notification.
• Send SMS (Optional Fallback) extends Transmit GPS Location with an <<extend>>
relationship, indicating it activates only when a contact does not have the mobile application
installed.
• The Start Acknowledgment Timer is included within Trigger Emergency Escalation,
enforcing that escalation cannot occur without first providing the driver a window to respond.
Modules 5 & 7 – Mobile Application User Interactions
This diagram captures all user-facing interactions within the mobile application. The Vehicle Owner
/ Driver is the primary actor, with the Backend Server depicted as a secondary actor to represent server-
side validation and data persistence.
COMSATS University Islamabad | BS Artificial Intelligence | Page 19

SRS – Vision Based Driver Monitoring and Safety Assistance System
Figure 1.4 – Use Case Diagram: Mobile App User Interactions (Modules 5 & 7)
Six primary use cases are identified for the Vehicle Owner: account registration, login with JWT
authentication, event log viewing, emergency contact management, system settings configuration, and
video clip retrieval. The <<include>> relationships connect Login to Validate Credentials and Manage
Emergency Contacts to Validate Contact Limit (max 5), reflecting mandatory business rules enforced
by the backend.
Module 8 – Web-Based Administrative Dashboard
This diagram models administrative and fleet management interactions with the web dashboard. Two
actors are identified: the System Administrator (full access) and the Fleet Manager (read-only access
to monitoring and analytics).
COMSATS University Islamabad | BS Artificial Intelligence | Page 20

SRS – Vision Based Driver Monitoring and Safety Assistance System
Figure 1.5 – Use Case Diagram: Web-Based Administrative Dashboard (Module 8)
The Fleet Manager actor has access only to monitoring and analytics use cases, while the System
Administrator has full access including user account management and system configuration. The
Refresh Data (5-second interval) use case is included within View Real-time Driver Status,
emphasizing that real-time monitoring requires automated data refresh and is not a purely static view.
COMSATS University Islamabad | BS Artificial Intelligence | Page 21

SRS – Vision Based Driver Monitoring and Safety Assistance System
2.5 Requirement Identifying Technique
For this project, two complementary requirement identification techniques are applied. Mockup-Based
Requirement Analysis is used for all frontend interactions in the mobile application and web
dashboard, where user interface mockups are created using Figma or Balsamiq. Each screen is
assigned a Mockup ID, and functional requirements are derived from interactive UI elements on each
screen. For backend and edge device processes such as real-time video inference, alert triggering, GPS
transmission, and event recording, the Event-Response Table technique is applied to capture system
responses to specific detected events. This dual approach ensures comprehensive coverage of both
user-facing and automated system behaviors.
2.6 Functional Requirements
2.6.1 Module 1 – Driver Monitoring and Analysis
Feature (from Functional Requirement (FR-ID: Business Rule
Mockup / Event) Statement)
Live Camera Stream FR1.1: The system shall continuously capture Camera must be active at
live video frames from the in-vehicle camera all times when the
at a minimum of 15 fps. vehicle is in operation.
Drowsiness FR1.2: The system shall detect driver EAR threshold
Detection drowsiness by analyzing eye aspect ratio and configurable between
head pose, triggering a drowsiness event when 0.20 and 0.30; default
the EAR falls below a configurable threshold 0.25.
for more than 2 consecutive seconds.
Emotion Analysis FR1.3: The system shall classify the driver’s Angry or fear states
emotional state into one of seven categories sustained for more than 3
(angry, disgust, fear, happy, neutral, sad, seconds shall trigger a
surprise) using a CNN model and flag soft alert.
distressed emotional states.
Inattentiveness FR1.4: The system shall detect driver Head pose deviation
Detection inattentiveness by monitoring head pose threshold configurable by
deviation beyond 30 degrees from the the user.
forward-facing position for more than 2
seconds.
Table 2.3: Functional Requirements – Module 1
2.6.2 Module 2 – Edge AI Processing Unit
Feature Functional Requirement Business Rule
COMSATS University Islamabad | BS Artificial Intelligence | Page 22

SRS – Vision Based Driver Monitoring and Safety Assistance System
On-Device Inference FR2.1: The system shall execute all AI model Video frames must not
inference on the Raspberry Pi without leave the device for
transmitting raw video data to external inference.
servers.
Model Optimization FR2.2: AI models shall be converted to Inference latency must
TensorFlow Lite or ONNX format and not exceed 200ms per
quantized to INT8 precision to meet real-time frame under normal
inference targets on ARM hardware. conditions.
Multi-Model FR2.3: The system shall manage concurrent CPU utilization must not
Pipeline execution of drowsiness, emotion, and safety exceed 85% to maintain
detection models within the available system responsiveness.
computational budget of the Raspberry Pi.
Table 2.4: Functional Requirements – Module 2
2.6.3 Module 3 – Alert and Emergency Escalation (Edge)
Feature Functional Requirement Business Rule
Audio/Visual Alert FR3.1: The system shall generate an audio Alert must persist until
buzzer alert and activate a connected LED acknowledged or
indicator within 2 seconds of detecting a escalation triggers.
confirmed unsafe driver state.
Acknowledgment FR3.2: The system shall provide a physical Acknowledgment
Mechanism button or proximity-based mechanism for the window configurable
driver to acknowledge and dismiss active between 5 and 30
alerts. seconds.
Emergency FR3.3: If a safety alert is not acknowledged Escalation must not
Escalation within the configured window, the system trigger for single-frame
shall transmit an emergency event with events; sustained events
current GPS coordinates to the mobile required.
application for forwarding to emergency
contacts.
Table 2.5: Functional Requirements – Module 3
2.6.4 Module 4 – Vehicle Safety Enhancements
Feature Functional Requirement Business Rule
Unauthorized FR4.1: The system shall detect and alert the Alert only triggers when
Occupant Detection vehicle owner when an unrecognized the vehicle is parked and
individual is detected inside the vehicle using the engine is off.
face recognition.
Key Left Inside FR4.2: The system shall detect and alert the Alert must be generated
driver when vehicle keys or fobs are detected within 10 seconds of
inside the cabin after the door is closed, using door closure event.
object detection.
Event-Based Video FR4.3: The system shall record a 30-second Older recordings shall be
Recording video clip (15 seconds before and 15 seconds automatically deleted
after the triggering event) whenever a safety when storage exceeds
event is confirmed, storing it locally on the 80% capacity.
device.
Table 2.6: Functional Requirements – Module 4
COMSATS University Islamabad | BS Artificial Intelligence | Page 23

SRS – Vision Based Driver Monitoring and Safety Assistance System
2.6.5 Module 5 – User Authentication (Mobile App)
Feature (from Functional Requirement Business Rule
Mockup)
M1 – Registration FR5.1: The system shall allow a new user to Duplicate email
Screen register using a valid email address and registration must be
password; the system shall validate email rejected with an
format and enforce minimum 8-character informative error
passwords. message.
M2 – Login Screen FR5.2: The system shall authenticate After 5 consecutive failed
registered users using email and password login attempts, the
credentials and issue a JWT access token account shall be locked
valid for 24 hours upon successful for 15 minutes.
authentication.
M3 – Session FR5.3: The system shall automatically refresh Refresh token validity
Management expired JWT tokens without requiring user re- period: 7 days.
login, provided the refresh token remains
valid.
M4 – Access Control FR5.4: The system shall restrict access to Role hierarchy: Owner >
administrative configuration features to Family Member > Guest.
authenticated users with the Owner role only.
Table 2.7: Functional Requirements – Module 5
2.6.6 Module 6 – Alert Management and Emergency Escalation (Mobile App)
Feature (from Functional Requirement Business Rule
Mockup)
M5 – Alert FR6.1: The system shall display real-time Notifications must persist
Notification push notifications on the mobile application until acknowledged by
within 3 seconds of an alert being generated the user.
by the edge device.
M6 – Alert FR6.2: The system shall allow the Acknowledgment must
Acknowledgment authenticated driver to acknowledge active be transmitted back to the
alerts through the mobile application, edge device.
canceling the escalation timer.
M7 – Emergency FR6.3: Upon receiving an escalation trigger GPS coordinates must be
Escalation from the edge device, the system shall send current at time of
emergency notifications containing GPS escalation, not cached.
coordinates to all designated emergency
contacts (up to 5) via push notification or
SMS.
M8 – Contact FR6.4: The system shall allow the vehicle At least 1 emergency
Management owner to add, edit, and remove emergency contact must be
contacts with a minimum of 1 and maximum configured for escalation
of 5 contacts configured. to function.
Table 2.8: Functional Requirements – Module 6
2.6.7 Module 7 – Monitoring, Logs, and Configuration (Mobile App)
Feature (from Functional Requirement Business Rule
Mockup)
COMSATS University Islamabad | BS Artificial Intelligence | Page 24

SRS – Vision Based Driver Monitoring and Safety Assistance System
M9 – Event Log FR7.1: The system shall display a paginated Logs must be retained for
Screen log of all safety events with timestamps, event a minimum of 30 days.
type, severity level, and action taken, sorted
by most recent.
M10 – Video FR7.2: The system shall allow the vehicle Video retrieval requires
Playback owner to retrieve and play back event- active Wi-Fi connection
triggered video clips stored on the edge device to the edge device.
through the mobile application.
M11 – System FR7.3: The system shall allow the vehicle Configuration changes
Configuration owner to configure alert sensitivity thresholds, must take effect on the
acknowledgment time windows, and edge device within 5
notification preferences through the mobile seconds.
application settings screen.
Table 2.9: Functional Requirements – Module 7
2.6.8 Module 8 – Web-Based Dashboard
Feature (from Functional Requirement Business Rule
Mockup)
M12 – Monitoring FR8.1: The web dashboard shall display real- Dashboard accessible
Dashboard time driver monitoring status, active alerts, only to authenticated
and recent event summaries updated at a administrators and fleet
minimum of 5-second intervals. managers.
M13 – Analytics FR8.2: The system shall provide interactive Charts shall be
Charts charts visualizing alert frequency, event type exportable as PNG or
distribution, and system uptime over CSV.
configurable time periods (daily, weekly,
monthly).
M14 – User FR8.3: The system administrator shall be able Deactivated users lose
Management to create, view, edit, and deactivate user immediate access; data is
accounts and assign roles through the web retained for 90 days.
dashboard.
Table 2.10: Functional Requirements – Module 8
2.7 Non-Functional Requirements
2.7.1 Reliability
• REL-1: The edge device monitoring system shall achieve a Mean Time Between Failures
(MTBF) of at least 200 hours of continuous operation under normal in-vehicle conditions.
• REL-2: The system shall recover automatically from a camera feed interruption within 5
seconds without requiring user intervention.
• REL-3: Alert generation must not fail silently; if the alert subsystem encounters an error, it
shall log the failure and attempt a retry within 2 seconds.
• REL-4: The mobile application shall handle network disconnections gracefully, queuing
alerts locally and synchronizing when connectivity is restored.
2.7.2 Usability
COMSATS University Islamabad | BS Artificial Intelligence | Page 25

SRS – Vision Based Driver Monitoring and Safety Assistance System
• USE-1: A new user shall be able to complete the initial setup of the mobile application
including registration, device pairing, and emergency contact configuration within 10
minutes without external assistance.
• USE-2: Safety alerts on the mobile application shall be presented using color-coded severity
indicators (red for critical, amber for warning) and brief descriptive text not exceeding 20
words.
• USE-3: The mobile application shall provide a one-tap acknowledgment mechanism for
active alerts, accessible from the notification shade without requiring full app navigation.
2.7.3 Performance
• PER-1: The drowsiness and emotion detection pipeline on the edge device shall process
video frames at a minimum rate of 15 frames per second under normal operating conditions.
• PER-2: End-to-end latency from event detection on the edge device to push notification
delivery on the mobile application shall not exceed 5 seconds under stable network
conditions.
• PER-3: The web dashboard shall fully load and render within 4 seconds on a standard
broadband connection (20 Mbps or faster).
• PER-4: The system shall sustain continuous operation for at least 8 hours without
performance degradation exceeding 10% in inference throughput.
2.7.4 Security
• SEC-1: All communication between the mobile application, web dashboard, and backend
server shall be encrypted using TLS 1.2 or higher.
• SEC-2: User credentials shall be stored using bcrypt hashing with a minimum cost factor of
12; plaintext passwords must never be stored or logged.
• SEC-3: The system shall implement role-based access control, ensuring that users can only
access data and features corresponding to their assigned role.
• SEC-4: Video recordings stored on the edge device shall be accessible only to authenticated
application users through secure retrieval channels.
2.8 External Interface Requirements
2.8.1 User Interface Requirements
• UI-1: The mobile application shall follow Material Design 3 guidelines for consistency,
accessibility, and visual clarity across Android devices.
• UI-2: Font sizes in the mobile application shall not be smaller than 14sp to ensure readability
for users with moderate visual impairment.
• UI-3: The web dashboard shall be responsive and adapt to screen resolutions from 1280x720
to 4K without horizontal scrolling.
• UI-4: All alert screens shall include both textual and iconographic representation of the alert
type to support comprehension for non-expert users.
2.8.2 Software Interfaces
COMSATS University Islamabad | BS Artificial Intelligence | Page 26

SRS – Vision Based Driver Monitoring and Safety Assistance System
• SI-1: The edge device shall communicate with the mobile application backend using MQTT
over port 1883 (or 8883 with TLS) for real-time alert and event data transmission.
• SI-2: The mobile application shall interface with Google Maps API or OpenStreetMap API
to display GPS location data on emergency escalation notifications.
• SI-3: The web dashboard shall consume a RESTful JSON API exposed by the Node.js
backend server over HTTPS for all data retrieval and management operations.
• SI-4: Firebase Cloud Messaging (FCM) shall be used as the push notification delivery
service for mobile alert transmission.
2.8.3 Hardware Interfaces
• HI-1: The system shall interface with a Raspberry Pi Camera Module v2 or compatible USB
camera via the CSI or USB interface, capable of capturing video at 1080p resolution at 30
fps.
• HI-2: The system shall interface with a connected GPS module (e.g., NEO-6M or equivalent)
via UART or USB to obtain real-time location data.
• HI-3: Alert hardware including an active buzzer and LED indicator shall be connected to the
Raspberry Pi GPIO pins and controlled by the alert management module.
2.8.4 Communication Interfaces
• CI-1: The edge device shall use Wi-Fi (IEEE 802.11 b/g/n) or mobile hotspot connectivity to
communicate with the backend server and mobile application.
• CI-2: Emergency GPS escalation notifications to emergency contacts shall be delivered via
Firebase Cloud Messaging push notification and optionally via SMS using Twilio or a
similar SMS gateway.
• CI-3: Internal communication between the edge device modules (monitoring, alert,
recording) shall use Python inter-process communication or shared memory queues to
minimize latency.
COMSATS University Islamabad | BS Artificial Intelligence | Page 27

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 3: Design and Architecture
This chapter presents the high-level architectural design of the Vision Based Driver Monitoring and
Safety Assistance System. It describes the system’s conceptual architecture, architectural style, design
models, and data design.
3.1 System Architecture Overview
The system is composed of three primary architectural layers: the Edge Device Layer, the Mobile
Application Layer, and the Web Dashboard Layer. Each layer communicates through defined
interfaces and serves a distinct role in the overall safety ecosystem.
The Edge Device Layer, implemented on a Raspberry Pi 4, is the core intelligence hub of the system.
It hosts the camera interface, AI model inference pipeline, alert generation hardware, GPS module
interface, and local video storage. This layer operates autonomously and does not require internet
connectivity for its core detection and alert functions. It communicates outward to the mobile backend
via MQTT for real-time event and alert transmission.
The Mobile Application Layer serves as the primary user interface for the vehicle owner. It connects
to the backend server via RESTful APIs and MQTT to receive real-time alerts, manage emergency
contacts, retrieve event logs and video clips, and configure system parameters. Emergency escalation
from this layer distributes GPS coordinates to emergency contacts via Firebase Cloud Messaging.
The Web Dashboard Layer provides an administrative interface for system operators and fleet
managers. It connects to the same backend API to access analytics, event logs, user management, and
system configuration. This layer is accessible through a standard web browser and is hosted on a
remote or local server.
3.2 Technologies and Services by Component
Component Description Technology Used Security Mechanism
Edge Device (RPi) AI inference, alert Python, OpenCV, Local-only processing,
generation, event TFLite, ONNX no raw data egress
recording
Mobile App Driver interface for Flutter / React Native JWT Auth, TLS, Input
Frontend alerts and Validation
configuration
Backend API Business logic, data Node.js / Django, JWT, OAuth 2.0,
management, MQTT MQTT Broker HTTPS
broker
Database Event logs, user data, PostgreSQL / Role-based Access
configurations Firebase Control, Encryption at
Rest
COMSATS University Islamabad | BS Artificial Intelligence | Page 28

SRS – Vision Based Driver Monitoring and Safety Assistance System
Web Dashboard Admin monitoring React.js, Node.js Admin Auth, 2FA
and management optional
interface
Push Notification Real-time alert and Firebase Cloud Server-side API Key,
Service emergency delivery Messaging (FCM) Secure Tokens
GPS Integration Location data for NEO-6M GPS Location data
emergency escalation Module, Google transmitted only on
Maps API escalation trigger
Table 3.1: Technologies, Components, and Security Mechanisms
3.3 Architecture Style / Pattern
The system employs a layered client-server architecture combined with an event-driven pattern for
real-time safety processing. The edge device operates as a standalone embedded system with an event-
driven internal pipeline, where each detection module publishes events to a shared internal queue
consumed by the alert and recording modules. The mobile application and web dashboard follow a
client-server model with RESTful API communication for non-real-time operations and MQTT-based
publish-subscribe messaging for real-time alert delivery. The backend adopts an MVC (Model-View-
Controller) pattern to separate data management, business logic, and API response handling. This
hybrid architecture is well-suited for systems that require both real-time responsiveness on constrained
hardware and flexible cloud-assisted management capabilities.
3.4 Design Models
The following design models are to be developed and included in the final implementation report.
Descriptions are provided here as placeholders for the SRS phase.
3.4.1 Activity Diagram
An activity diagram will be developed to model the complete real-time driver monitoring workflow:
from camera frame capture through AI inference, alert determination, driver acknowledgment
decision, and emergency escalation. Separate activity diagrams will model the mobile application alert
reception flow and the administrative dashboard interaction flow.
3.4.2 Class Diagram
A class diagram will be developed to represent the primary classes of the system including:
DriverMonitor, DrowsinessDetector, EmotionClassifier, AlertManager, GPSModule,
EmergencyEscalation, EventRecorder, UserAccount, EmergencyContact, EventLog, and
DashboardController. Associations, multiplicities, and key methods will be defined for each class.
3.4.3 Sequence Diagram
Sequence diagrams will be developed for the following key scenarios: (1) Driver Drowsiness
Detection and Alert Generation, (2) Emergency Escalation with GPS Transmission, (3) User
Registration and Device Pairing, and (4) Event Log Retrieval from Edge Device to Mobile
Application.
3.4.4 State Machine Diagram
COMSATS University Islamabad | BS Artificial Intelligence | Page 29

SRS – Vision Based Driver Monitoring and Safety Assistance System
A behavioral state machine diagram will model the lifecycle of a SafetyAlert object, transitioning
through states: Detected → Active → Acknowledged / Escalated → Resolved, with events and guards
defining each transition.
3.5 Data Design
The primary data entities and their key attributes are described below:
Entity Key Attributes Description
User user_id, email, password_hash, Stores registered user accounts for
role, created_at the mobile and web interfaces.
EmergencyContact contact_id, user_id, name, Stores emergency contacts
phone_number, email, priority associated with a vehicle owner.
SafetyEvent event_id, event_type, severity, Logs each detected safety event
timestamp, gps_lat, gps_lng, with metadata and response status.
acknowledged, escalated
VideoClip clip_id, event_id, file_path, References locally stored event-
duration, created_at triggered video recordings.
SystemConfig config_id, user_id, ear_threshold, Stores per-user system
acknowledgment_window, configuration parameters.
alert_sensitivity
AlertLog log_id, event_id, alert_type, Tracks alert delivery attempts and
sent_at, delivery_status confirmation status.
Table 3.2: Data Design – Primary Entities
COMSATS University Islamabad | BS Artificial Intelligence | Page 30

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 4: Implementation
This chapter outlines the project methodology, AI model training and evaluation approach, security
techniques applied, external APIs and SDKs utilized, user interface design, and deployment strategy
for the Vision Based Driver Monitoring and Safety Assistance System.
4.1 Project Methodology and Algorithms
4.1.1 Project Methodology (Step-by-Step Approach)
The project follows an Iterative and Incremental Development methodology, well-suited for AI-
integrated embedded systems where requirements and model performance are refined through
repeated cycles. The development proceeds through the following phases:
• Phase 1 – Data Collection and Preparation: Collection of publicly available datasets (MRL
Eye Dataset for drowsiness, FER-2013/AffectNet for emotion recognition) and controlled in-
vehicle data collection for system-specific fine-tuning.
• Phase 2 – Model Training and Optimization: Training of drowsiness detection and emotion
classification models using TensorFlow/PyTorch, followed by conversion to TensorFlow
Lite / ONNX format and INT8 quantization for edge deployment.
• Phase 3 – Edge Device Integration: Deployment of optimized models on Raspberry Pi,
integration of camera capture pipeline, GPS module, and alert hardware, followed by real-
time inference testing and latency benchmarking.
• Phase 4 – Mobile Application Development: Development of Flutter-based mobile
application covering user authentication, real-time alert reception via MQTT, emergency
contact management, and event log viewing.
• Phase 5 – Web Dashboard Development: Development of React.js administrative dashboard
with backend Node.js API, database integration, and analytics visualization.
• Phase 6 – System Integration and Testing: End-to-end integration testing of all modules,
performance benchmarking, usability evaluation, and iterative refinement based on test
results.
4.1.2 Key Algorithms
• Eye Aspect Ratio (EAR) Algorithm: Computes the ratio of vertical to horizontal eye
landmark distances using Dlib or MediaPipe facial landmarks to quantify eye openness. A
sustained EAR below threshold triggers a drowsiness event.
• Convolutional Neural Network (CNN) for Emotion Classification: A lightweight
MobileNetV2-based classifier trained on facial expression datasets to output probability
distributions across seven emotion classes.
• Head Pose Estimation: Uses solvePnP with 3D facial landmark correspondences to estimate
yaw, pitch, and roll angles, detecting forward-facing deviation indicating inattentiveness.
• FIFO Event Queue with Temporal Filtering: All detected events are passed through a
temporal consistency filter requiring a minimum sustained duration before triggering alerts,
reducing false positive rates.
COMSATS University Islamabad | BS Artificial Intelligence | Page 31

SRS – Vision Based Driver Monitoring and Safety Assistance System
4.2 Training Results and Model Evaluation (Mandatory for AI/ML
Projects)
Model evaluation will be conducted using standard classification metrics including Accuracy,
Precision, Recall, F1-Score, and Confusion Matrix analysis. For drowsiness detection, the system
targets a minimum Recall of 90% on the test set (prioritizing missed detections as the more critical
failure mode). For emotion classification, an overall accuracy of at least 75% across seven classes is
targeted. Inference latency benchmarks will be reported for each model independently and for the
combined multi-model pipeline on the Raspberry Pi 4 hardware. Results will be documented in the
final implementation report with training and validation curves.
4.3 Security Techniques
• JWT (JSON Web Token) Authentication: All API requests from the mobile application and
web dashboard are authenticated using short-lived JWT access tokens and longer-lived
refresh tokens stored securely on the client.
• TLS Encryption: All network communication between system components is encrypted using
TLS 1.2 or higher, preventing interception of alert data and user credentials.
• bcrypt Password Hashing: User passwords are hashed using bcrypt with a cost factor of 12
before storage; plaintext passwords are never persisted.
• Role-Based Access Control (RBAC): User roles (Owner, Administrator, Guest) restrict
access to sensitive operations and data based on assigned permissions.
4.4 External APIs / SDKs
API / SDK Purpose Rationale
Firebase Cloud Push notification delivery for real- Reliable, scalable, free-tier push
Messaging (FCM) time safety alerts to mobile notification service with broad
application. Android support.
Google Maps API / Display GPS location on Accurate mapping and reverse
OpenStreetMap emergency escalation notifications. geocoding for emergency
responders.
TensorFlow Lite / On-device AI model inference on Optimized for ARM hardware with
ONNX Runtime Raspberry Pi. INT8 quantization support.
MediaPipe Face Mesh Real-time facial landmark High accuracy, GPU-optional, runs
detection for drowsiness and head efficiently on Raspberry Pi.
pose estimation.
Twilio SMS API SMS delivery of emergency Fallback for contacts without the
(optional) location to contacts without mobile mobile application installed.
app.
Table 4.1: External APIs and SDKs
4.5 User Interface
The following screens have been designed as mockups for the mobile application. Final high-fidelity
mockups developed in Figma will be included in the appendix of the final report.
COMSATS University Islamabad | BS Artificial Intelligence | Page 32

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Login Screen : Email and password fields, login button, register link, and forgot password
option.
• Home Screen / Dashboard: Real-time driver status indicator (Safe / Warning / Critical), last
event summary, active alert banner, and quick navigation to Logs, Contacts, and Settings.
COMSATS University Islamabad | BS Artificial Intelligence | Page 33

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Alert Screen : Full-screen alert notification with event type icon, description, timestamp, and
prominent Acknowledge button. Red background for critical alerts, amber for warnings.
COMSATS University Islamabad | BS Artificial Intelligence | Page 34

SRS – Vision Based Driver Monitoring and Safety Assistance System
COMSATS University Islamabad | BS Artificial Intelligence | Page 35

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Emergency Escalation Screen : Map view showing GPS location, list of notified contacts,
escalation timestamp, and status of notification delivery.
• Event Logs Screen : Paginated list of past events with type, severity badge, timestamp, and
tap-to-expand detail view with option to play associated video clip.
COMSATS University Islamabad | BS Artificial Intelligence | Page 36

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Settings Screen : Sliders for EAR threshold, acknowledgment window, and alert sensitivity;
toggle for SMS fallback; emergency contact management link.
COMSATS University Islamabad | BS Artificial Intelligence | Page 37

SRS – Vision Based Driver Monitoring and Safety Assistance System
• Web Dashboard : Side-navigation layout with Overview, Analytics, User Management, and
System Settings sections; real-time status panel for active monitoring sessions.
COMSATS University Islamabad | BS Artificial Intelligence | Page 38

SRS – Vision Based Driver Monitoring and Safety Assistance System
4.6 Deployment
The system is deployed as a prototype across three environments. The Raspberry Pi 4 edge device is
installed inside the vehicle dashboard area with the camera positioned to capture the driver’s face. The
device runs a startup script on boot that initializes all monitoring, recording, and communication
modules automatically. The mobile application is distributed as an APK for Android testing devices.
The backend server and web dashboard are deployed on a local development server or AWS EC2
instance for prototype evaluation. All environment-specific configurations (MQTT broker address,
API endpoints, FCM credentials) are managed through a centralized configuration file.
COMSATS University Islamabad | BS Artificial Intelligence | Page 39

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 5: Testing and Evaluation
This  chapter  describes  the  testing  strategy  applied  to  validate  the  correctness,  reliability,  and
performance  of  the  Vision  Based  Driver  Monitoring  and  Safety  Assistance  System  across  all
functional modules.
5.1  Unit Testing
Unit testing is applied to individual functions and classes within the edge device codebase and backend
services. The following components are subject to unit testing:
•  EAR Calculation Function: Validated against known landmark coordinates to verify correct
ratio computation and threshold comparison logic.
•  Alert Trigger Logic: Tested for correct alert state transitions with simulated event durations
below, at, and above the configured threshold.
•  JWT Generation and Validation: Tested for correct token expiry, signature verification, and
invalid token rejection.
•  GPS Data Parsing: Validated against sample NMEA sentences from the GPS module to
ensure correct coordinate extraction.
•  Event Log CRUD Operations: Backend API handlers tested using pytest and Postman for
correct database interaction and response codes.
5.2  Functional Testing
Functional testing validates that each documented functional requirement is correctly implemented.
Test cases are derived directly from the functional requirements table in Section 2.6. Representative
test cases include:
| TC-ID  | FR Reference  | Test Description  | Expected  | Status  |
| ------ | ------------- | ----------------- | --------- | ------- |
Result
| TC-01  | FR1.2  | Simulate sustained EAR   | Alert       | To Be Tested  |
| ------ | ------ | ------------------------ | ----------- | ------------- |
|        |        | below 0.25 for 2.5       | generated   |               |
|        |        | seconds; verify          | within 2    |               |
|        |        | drowsiness alert fires.  | seconds of  |               |
threshold
breach.
TC-02  FR3.3  Simulate unacknowledged  Emergency  To Be Tested
|     |     | drowsiness alert; verify  | notification   |     |
| --- | --- | ------------------------- | -------------- | --- |
|     |     | GPS escalation triggers   | sent with GPS  |     |
|     |     | after configured window.  | coordinates.   |     |
TC-03  FR5.2  Attempt login with correct  JWT token  To Be Tested
|        |        | credentials; verify JWT     | received;     |               |
| ------ | ------ | --------------------------- | ------------- | ------------- |
|        |        | issued and app navigates    | home screen   |               |
|        |        | to home screen.             | displayed.    |               |
| TC-04  | FR6.3  |                             |               | To Be Tested  |
|        |        | Trigger escalation; verify  | All contacts  |               |
|        |        | all configured emergency    | notified      |               |
|        |        | contacts receive FCM        | within 5      |               |
|        |        | notification.               | seconds.      |               |
COMSATS University Islamabad  |  BS Artificial Intelligence  |  Page 40

SRS – Vision Based Driver Monitoring and Safety Assistance System
TC-05 FR4.3 Trigger safety event; Video file To Be Tested
verify 30-second video created with
clip is stored on device correct event
with correct metadata. timestamp.
Table 5.1: Functional Test Cases
5.3 Business Rules Testing
Decision table testing is applied to validate system behavior under combinations of business rule
conditions. Key business rules tested include: alert escalation based on acknowledgment window and
alert type; emergency contact notification rules based on contact count and escalation trigger; and role-
based access control behavior for different user roles attempting restricted operations. Decision tables
will be formalized in the test appendix of the final report.
5.4 Integration Testing
Integration testing validates the correct interaction between system modules and components across
system boundaries. The following integration test scenarios are planned:
• Edge-to-Mobile Integration: End-to-end test of drowsiness detection on the edge device
triggering an alert visible on the mobile application within the specified 5-second latency
target.
• Mobile-to-Backend Integration: Test of user registration, login, event log retrieval, and
configuration update flows between the mobile application and backend API.
• Emergency Escalation Integration: Full pipeline test from unacknowledged edge event
through backend escalation to FCM notification delivery on emergency contact devices.
• Dashboard-to-Backend Integration: Test of analytics data retrieval, user management
operations, and real-time event status display on the web dashboard.
COMSATS University Islamabad | BS Artificial Intelligence | Page 41

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 6: Conclusion and Future Work
6.1 Conclusion
The Vision Based Driver Monitoring and Safety Assistance System addresses a critical and
underserved need for intelligent, affordable, and privacy-preserving driver safety technology. By
deploying optimized computer vision models on an edge device, the system achieves real-time
drowsiness detection, emotion analysis, and behavioral monitoring without the latency, privacy risks,
or connectivity dependencies of cloud-based approaches. The integration of an automated emergency
escalation mechanism with GPS location transmission represents a meaningful advancement over
existing academic prototypes and makes the system practically useful in real-world emergency
scenarios. The companion mobile application and web dashboard provide a complete user experience
encompassing configuration, monitoring, alert management, and analytics. The project demonstrates
that advanced driver safety capabilities previously restricted to premium vehicles can be democratized
through careful application of embedded AI, edge computing, and modern mobile development
technologies. The completed prototype will provide a strong experimental foundation for further
research and development toward a production-ready aftermarket driver safety product.
6.2 Future Work
• Multi-Passenger Monitoring: Extend the monitoring capability to simultaneously track
multiple passengers in the vehicle, enabling more comprehensive vehicle safety analytics.
• Advanced Emotion-Behavior Fusion: Develop a fused model that jointly processes emotion
recognition and behavioral cues (head pose, eye movement, body posture) for more robust
and context-aware driver state estimation.
• Night Vision and Low-Light Enhancement: Integrate an infrared camera module and low-
light image enhancement preprocessing to maintain detection accuracy in nighttime driving
conditions.
• OBD-II Vehicle Data Integration: Interface with the vehicle’s OBD-II port to incorporate
real-time vehicle speed, acceleration, and engine state data for richer contextual safety
analysis.
• Federated Learning for Model Improvement: Explore privacy-preserving federated learning
to improve model accuracy across a fleet of deployed devices without centralizing sensitive
video data.
• Production Packaging and Regulatory Compliance: Develop a ruggedized hardware package
suitable for permanent vehicle installation and explore compliance pathways with automotive
safety standards for commercial deployment.
COMSATS University Islamabad | BS Artificial Intelligence | Page 42

SRS – Vision Based Driver Monitoring and Safety Assistance System
Chapter 7: References
Books
• Sommerville, I. Software Engineering, 10th ed. Boston, MA: Pearson Education, 2016, pp. 45–89.
• Pressman, R.S. and Maxim, B.R. Software Engineering: A Practitioner’s Approach, 9th ed. New
York, NY: McGraw-Hill, 2019, pp. 120–156.
• Goodfellow, I., Bengio, Y., and Courville, A. Deep Learning. Cambridge, MA: MIT Press, 2016, pp.
201–270.
• Szeliski, R. Computer Vision: Algorithms and Applications, 2nd ed. New York, NY: Springer, 2022,
pp. 150–220.
Journal Articles
• J. Doe and A. Smith. “Driver drowsiness detection using computer vision techniques.” Journal of
Intelligent Transportation Systems, vol. 18, pp. 45–60, March 2022.
• L. Chen and M. Patel. “Edge AI for real-time monitoring in automotive applications.” International
Journal of Computer Applications, vol. 174, pp. 15–22, August 2020.
• S. Kumar and R. Sharma. “Web-based dashboards for IoT-enabled vehicle monitoring systems.”
Journal of Embedded Systems, vol. 12, pp. 80–95, June 2021.
Conference Proceedings
• K. Brown and T. Wilson. “Real-time driver monitoring and alert system using AI.” Proceedings of
the International Conference on Software Engineering and Applications, 2019, pp. 112–118.
• S. Ahmed and R. Khan. “IoT-based vehicle safety and alert escalation systems.” Proc. International
Conference on Information Systems and Technology, 2020, pp. 98–104.
World Wide Web
• M. Duncan. “Trends in vehicle telematics and driver monitoring systems.” Internet:
https://www.telematicsnews.com, Jan. 10, 2025 [Dec. 15, 2025].
• Google Developers. “Firebase authentication and database documentation.” Internet:
https://firebase.google.com/docs, Mar. 15, 2025 [Dec. 15, 2025].
• OpenCV Team. “OpenCV documentation for Python.” Internet: https://docs.opencv.org, Feb. 5,
2025 [Dec. 15, 2025].
• Flutter Team. “Flutter development documentation.” Internet: https://docs.flutter.dev, Apr. 5, 2025
[Dec. 15, 2025].
• MediaPipe Team. “MediaPipe face mesh solution.” Internet:
https://developers.google.com/mediapipe, Mar. 1, 2025 [Dec. 15, 2025].
COMSATS University Islamabad | BS Artificial Intelligence | Page 43