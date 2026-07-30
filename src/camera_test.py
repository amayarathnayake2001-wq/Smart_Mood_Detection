import cv2

# Initialize the built-in laptop camera (0 is usually the default webcam)
# Using DirectShow to prevent MSMF errors on Windows
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("Error: Could not open laptop camera.")
    exit()

print("Camera connected! Press 'q' to exit the video stream.")

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    
    if not ret:
        print("Error: Failed to grab frame.")
        break

    # Display the live video feed in a window
    cv2.imshow('Laptop Camera Feed', frame)

    # Break the loop when the 'q' key is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera and close windows
cap.release()
cv2.destroyAllWindows()