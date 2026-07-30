import cv2
from deepface import DeepFace
import requests
import json

# Your exact Firebase Realtime Database Rest Endpoint URL
FIREBASE_URL = "https://mood-detection-eb7e1-default-rtdb.asia-southeast1.firebasedatabase.app/system_status.json"

# Initialize the laptop camera
cap = cv2.VideoCapture(0)

# Set resolution to a standard size to keep video smooth
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Error: Could not open laptop camera.")
    exit()

print("Camera initialized successfully! Starting video window...")
last_logged_emotion = ""
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to grab frame.")
        break

    frame_count += 1

    # Run AI analysis every 5 frames to keep the camera live stream perfectly smooth
    if frame_count % 5 == 0:
        try:
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if isinstance(analysis, list):
                analysis = analysis[0]
                
            dominant_emotion = analysis['dominant_emotion']
            
            # Get bounding box coordinates for your face
            region = analysis['region']
            x, y, w, h = region['x'], region['y'], region['w'], region['h']
            
            # Draw green bounding box and text on your face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"Mood: {dominant_emotion.upper()}", (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            # Synchronize with Firebase if your expression changes
            if dominant_emotion != last_logged_emotion:
                print(f"Syncing new mood to cloud: {dominant_emotion}")
                
                # Directly patch data to your Firebase node using a standard HTTP request
                payload = json.dumps({"current_emotion": dominant_emotion})
                requests.patch(FIREBASE_URL, data=payload)
                
                last_logged_emotion = dominant_emotion
                        
        except Exception as e:
            pass

    # Show the camera feed window immediately
    cv2.imshow('AI Mood Detection (Firebase Active)', frame)

    # Press 'q' to quit the window
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()