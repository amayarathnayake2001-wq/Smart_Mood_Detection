import cv2
from deepface import DeepFace

# Initialize the laptop camera
cap = cv2.VideoCapture(0)

print("Starting AI Emotion Detection Pipeline...")
print("Please wait a moment on the first run as models initialize.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    try:
        # DeepFace analyzes the current frame for emotion
        # actions=['emotion'] tells it to skip age/gender to keep it faster
        # enforce_detection=False prevents the script from crashing if no face is in view
        analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        
        # DeepFace returns a list of results if multiple faces are found; take the first one
        if isinstance(analysis, list):
            analysis = analysis[0]
            
        dominant_emotion = analysis['dominant_emotion']
        
        # Get face coordinates to draw a bounding box around your face
        region = analysis['region']
        x, y, w, h = region['x'], region['y'], region['w'], region['h']
        
        # Draw a bounding box around the detected face
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Overlay the detected emotion text above the bounding box
        cv2.putText(frame, f"Mood: {dominant_emotion.upper()}", (x, y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    
    except Exception as e:
        # If any analysis error happens, log it and keep the stream running smoothly
        pass

    # Display the AI integrated video feed
    cv2.imshow('AI Mood Detection Pipeline', frame)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()