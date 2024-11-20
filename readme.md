
# Control Panel

> Working on this still....
> Use Alternate if you got a low spec PI, you can use a vm to run the server or can do it locally

![Control Panel Banner](/images/Screenshot%20(1546).png)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [License](#license)
- [Contact](#contact)

## Overview
> Requires python 3.8+

Welcome to the **Control Panel**, an intuitive and powerful interface designed to manage and monitor an AI-powered voice assistant. Developed by **Leon**, a dedicated student at **UCSKM**, specifically for the **2024 Annual Function**, this Control Panel integrates real-time system monitoring, seamless text-based interactions, and customizable settings to enhance user experience.

![Control Panel Interface](/images/Screenshot%20(1551).png)

## Features

- **Real-Time System Monitoring**
  - **Assistant Status**: View whether the AI assistant is active or inactive.
  - **CPU Temperature**: Monitor the CPU temperature in real-time.
  - **CPU Usage**: Track the CPU usage percentage.
  - **Memory Usage**: Keep an eye on the memory consumption.

- **Interactive AI Assistant**
  - **Text Input**: Communicate with the AI assistant through a user-friendly text interface.
  - **Chat History**: Review past interactions with the assistant for reference.
  - **Current Speech**: View the latest speech input and AI responses.

- **Customizable Settings**
  - **Wake Word**: Set a custom wake word to activate the assistant.
  - **Voice Response**: Toggle voice responses on or off.
  - **Assistant Personality**: Choose between different assistant personalities (Default, Friendly, Professional).

- **User Interface Enhancements**
  - **Dark Mode**: Switch between light and dark themes for comfortable viewing in various lighting conditions.
  - **Smooth Animations**: Enjoy a seamless and responsive user experience with smooth transitions and animations.
  - **Kill Switch**: Instantly deactivate the assistant for security and control.

## Technologies Used

### Frontend

- **HTML5**
- **Tailwind CSS**: For rapid UI development and responsive design.
- **Inter Font**: A modern, versatile font for enhanced readability.
- **JavaScript**: Handling user interactions and API communications.
- **Marked.js**: Parsing Markdown content.
- **Highlight.js**: Syntax highlighting for code blocks.

### Backend

- **Python 3**
- **Flask**: A lightweight web framework for handling API requests.
- **SpeechRecognition**: Capturing and interpreting voice commands.
- **psutil**: Monitoring system performance and resource usage.
- **SQLite**: Lightweight database for storing settings and chat history.
- **g4f**: AI chat completion using GPT models.
- **pyttsx3**: Text-to-speech conversion for voice responses.

## Installation

Follow these steps to set up and run the Control Panel on your local machine.

### Prerequisites

- **Python 3.7+**: Ensure Python is installed on your system. You can download it from [python.org](https://www.python.org/downloads/).
- **Git**: For cloning the repository. Download from [git-scm.com](https://git-scm.com/downloads).

### Steps

1. **Clone the Repository**

   ```bash
   git clone https://github.com/harshitkumar9030/speech_gpt.git
   cd control-panel
   ```

2. **Create a Virtual Environment**

   It's recommended to use a virtual environment to manage dependencies.

   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**

   - **Windows**

     ```bash
     venv\Scripts\activate
     ```

   - **macOS/Linux**

     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   *If `requirements.txt` is not provided, install the necessary packages manually:*

   ```bash
   pip install flask flask-cors speechrecognition psutil pyttsx3 g4f
   ```

5. **Initialize the Database**

   The application uses SQLite for storing settings and chat history. Initialize the database by running:

   ```bash
   python main.py
   ```


6. **Run the Application**

   ```bash
   python main.py
   ```

   The Control Panel should now be accessible at `http://localhost:5000`.

## Usage

1. **Access the Control Panel**

   Open your web browser and navigate to `http://localhost:5000` to access the Control Panel interface.

2. **Interacting with the AI Assistant**

   - **Wake Word Activation**: Say the wake word (default is "hello") to activate the assistant.
   - **Text Input**: Type your queries or commands into the text input field and click "Send" to interact with the assistant.
   - **Chat History**: Review past interactions in the Chat History section.
   - **Current Speech**: View the latest speech input and AI responses in real-time.

3. **Adjusting Settings**

   - **Wake Word**: Change the wake word by editing the text field in the Settings section.
   - **Voice Response**: Toggle voice responses on or off using the switch.
   - **Assistant Personality**: Select the desired personality for the assistant from the dropdown menu.
   - **Save Settings**: Click the "Save Settings" button to apply changes.

4. **Theme Toggle**

   - Click the sun/moon icon to switch between light and dark modes for a comfortable viewing experience.

5. **Kill Switch**

   - Click the "Kill Switch" button to immediately deactivate the assistant.


## Contributing

Contributions are welcome! If you'd like to contribute to this project, please follow these steps:

1. **Fork the Repository**

2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeatureName
   ```

3. **Commit Your Changes**

   ```bash
   git commit -m "Add some feature"
   ```

4. **Push to the Branch**

   ```bash
   git push origin feature/YourFeatureName
   ```

5. **Open a Pull Request**

   Describe your changes and submit the pull request for review.

## Acknowledgments

- **[Tailwind CSS](https://tailwindcss.com/)**: For providing a utility-first CSS framework.
- **[Inter Font](https://rsms.me/inter/)**: For the beautiful and versatile font.
- **[Flask](https://flask.palletsprojects.com/)**: For the lightweight web framework.
- **[SpeechRecognition](https://pypi.org/project/SpeechRecognition/)**: For enabling speech-to-text capabilities.
- **[psutil](https://psutil.readthedocs.io/)**: For system monitoring functionalities.
- **[g4f](https://github.com/)**: For AI chat completion.
- **[pyttsx3](https://pyttsx3.readthedocs.io/)**: For text-to-speech conversion.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For more information about this project, visit my personal website: [leoncyriac.me](https://leoncyriac.me)

Connect with me on [GitHub](https://github.com/harshitkumar9030)
---
