// Global variables
let currentDocumentId = null;
let audioPlayer = null;
let recognition = null;
let isRecording = false;
let currentSpeed = 1.0;
let currentVoiceProfile = 'default';
let speechQueue = [];
let isSpeaking = false;
let currentUtterance = null;
const MAX_CHUNK_LENGTH = 200; // Characters per speech chunk

// API Base URL
const API_BASE_URL = 'http://localhost:5000/api';

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    initializeSpeechRecognition();
    initializeVoiceNavigation();
});

function initializeApp() {
    // Check for saved preferences
    loadPreferences();
    
    // Create audio player
    audioPlayer = new Audio();
    setupAudioPlayer();
}

function setupEventListeners() {
    // File upload
    document.getElementById('fileUploadBtn').addEventListener('click', () => {
        document.getElementById('fileInput').click();
    });
    
    document.getElementById('fileInput').addEventListener('change', handleFileSelect);
    document.getElementById('urlSubmitBtn').addEventListener('click', handleUrlSubmit);
    
    // Voice control
    document.getElementById('micButton').addEventListener('click', toggleRecording);
    
    // Audio controls
    document.getElementById('playBtn').addEventListener('click', playAudio);
    document.getElementById('pauseBtn').addEventListener('click', pauseAudio);
    document.getElementById('stopBtn').addEventListener('click', stopAudio);
    document.getElementById('repeatBtn').addEventListener('click', repeatAudio);
    
    // Speed control
    document.getElementById('speedSlider').addEventListener('input', (e) => {
        currentSpeed = parseFloat(e.target.value);
        document.getElementById('speedValue').textContent = currentSpeed + 'x';
        if (audioPlayer) {
            audioPlayer.playbackRate = currentSpeed;
        }
    });
    
    // Voice profile
    document.getElementById('voiceProfile').addEventListener('change', (e) => {
        currentVoiceProfile = e.target.value;
    });
    
    // Accessibility controls
    document.getElementById('darkModeToggle').addEventListener('click', toggleDarkMode);
    document.getElementById('highContrastToggle').addEventListener('click', toggleHighContrast);
    document.getElementById('fontIncrease').addEventListener('click', increaseFont);
    document.getElementById('fontDecrease').addEventListener('click', decreaseFont);
    
    // Notes tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', switchTab);
    });
    
    // Quiz generation
    document.getElementById('generateQuizBtn').addEventListener('click', generateQuiz);
    
    // Chat
    document.getElementById('sendChatBtn').addEventListener('click', sendChatMessage);
    document.getElementById('voiceChatBtn').addEventListener('click', () => {
        startRecording('chat');
    });
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });
    
    // Export
    document.getElementById('exportBtn').addEventListener('click', exportData);
    
    // Play overview
    document.getElementById('playOverviewBtn').addEventListener('click', () => {
        const audioUrl = document.getElementById('playOverviewBtn').dataset.audioUrl;
        if (audioUrl) {
            playAudioFromUrl(audioUrl);
        }
    });
    
    // Keyboard shortcuts for speech control
    document.addEventListener('keydown', handleKeyboardShortcuts);
}

// ==================== VOICE NAVIGATION IMPROVEMENTS ====================

function initializeVoiceNavigation() {
    // Create voice status indicator if it doesn't exist
    if (!document.getElementById('voice-status')) {
        const status = document.createElement('div');
        status.id = 'voice-status';
        status.className = 'voice-status';
        status.innerHTML = '🎤 Microphone off';
        document.body.appendChild(status);
    }
    
    // Create speech controls
    createSpeechControls();
}

function createSpeechControls() {
    const controls = document.createElement('div');
    controls.id = 'speech-controls';
    controls.className = 'speech-controls';
    controls.innerHTML = `
        <button id="speech-play" class="speech-control-btn" title="Resume">▶️</button>
        <button id="speech-pause" class="speech-control-btn" title="Pause">⏸️</button>
        <button id="speech-stop" class="speech-control-btn" title="Stop">⏹️</button>
        <button id="speech-repeat" class="speech-control-btn" title="Repeat Last">🔄</button>
    `;
    
    document.body.appendChild(controls);
    
    // Add event listeners
    document.getElementById('speech-play').addEventListener('click', resumeSpeech);
    document.getElementById('speech-pause').addEventListener('click', pauseSpeech);
    document.getElementById('speech-stop').addEventListener('click', stopSpeech);
    document.getElementById('speech-repeat').addEventListener('click', repeatLastSpeech);
    
    // Hide controls initially
    controls.style.display = 'none';
}

function handleKeyboardShortcuts(e) {
    // Ctrl+Space to pause/resume
    if (e.ctrlKey && e.code === 'Space') {
        e.preventDefault();
        if (window.speechSynthesis.paused) {
            resumeSpeech();
        } else if (window.speechSynthesis.speaking) {
            pauseSpeech();
        }
    }
    
    // Escape to stop
    if (e.code === 'Escape' && window.speechSynthesis.speaking) {
        stopSpeech();
    }
    
    // Ctrl+R to repeat last
    if (e.ctrlKey && e.code === 'KeyR') {
        e.preventDefault();
        repeatLastSpeech();
    }
}

function initializeSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.maxAlternatives = 1;
        
        recognition.onstart = () => {
            isRecording = true;
            document.getElementById('micButton').classList.add('active');
            document.getElementById('voice-status').innerHTML = '🎤 Listening...';
            document.getElementById('voice-status').style.color = '#4CAF50';
            document.getElementById('recordingStatus').classList.remove('hidden');
        };
        
        recognition.onend = () => {
            isRecording = false;
            document.getElementById('micButton').classList.remove('active');
            document.getElementById('voice-status').innerHTML = '🎤 Microphone off';
            document.getElementById('voice-status').style.color = '#f44336';
            document.getElementById('recordingStatus').classList.add('hidden');
        };
        
        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            
            document.getElementById('commandResult').innerHTML = `<strong>You said:</strong> "${transcript}"`;
            
            if (event.results[0].isFinal) {
                processVoiceCommand(transcript.toLowerCase().trim());
            }
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            let errorMessage = 'Speech recognition error';
            
            if (event.error === 'no-speech') {
                errorMessage = 'No speech detected. Please try again.';
            } else if (event.error === 'audio-capture') {
                errorMessage = 'No microphone found. Please check your microphone.';
            } else if (event.error === 'not-allowed') {
                errorMessage = 'Microphone access denied. Please allow microphone access.';
            }
            
            showError(errorMessage);
            stopRecording();
        };
    } else {
        console.warn('Speech recognition not supported');
        document.getElementById('micButton').disabled = true;
        document.getElementById('micButton').title = 'Speech recognition not supported in this browser';
        document.getElementById('voice-status').innerHTML = '🎤 Not supported';
    }
}

function toggleRecording() {
    if (!recognition) {
        showError('Speech recognition is not supported in your browser');
        return;
    }
    
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording(context = 'command') {
    if (recognition) {
        try {
            recognition.start();
        } catch (error) {
            console.error('Failed to start recording:', error);
            showError('Failed to start recording. Please try again.');
        }
    }
}

function stopRecording() {
    if (recognition && isRecording) {
        recognition.stop();
    }
}

// ==================== ENHANCED VOICE COMMAND PROCESSING ====================

async function processVoiceCommand(command) {
    if (!command) return;
    
    console.log('Processing command:', command);
    
    // Check for control commands first (these don't need document)
    if (handleControlCommands(command)) {
        return;
    }
    
    if (!currentDocumentId) {
        speakText('Please upload a document first');
        showError('Please upload a document first');
        return;
    }
    
    // Show that we're processing
    document.getElementById('commandResult').innerHTML += `<br><strong>Processing:</strong> ${command}`;
    
    // Speak acknowledgment
    speakText(`Processing ${getCommandType(command)}`);
    
    try {
        const response = await fetch(`${API_BASE_URL}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: command,
                document_id: currentDocumentId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            await handleCommandResponse(data, command);
            
            // Announce completion after a short delay
            setTimeout(() => {
                speakText(`${getCommandType(command)} completed`);
            }, 1500);
        } else {
            showError(data.error || 'Failed to process command');
            speakText('Sorry, I could not process that command');
        }
    } catch (error) {
        console.error('Error processing command:', error);
        showError('Failed to connect to server');
        speakText('Connection error. Please try again.');
    }
}

function getCommandType(command) {
    if (command.includes('read')) return 'reading';
    if (command.includes('summarize')) return 'summarization';
    if (command.includes('quiz')) return 'quiz generation';
    if (command.includes('note')) return 'note taking';
    if (command.includes('bookmark')) return 'bookmarking';
    return 'command';
}

function handleControlCommands(command) {
    // Handle local control commands without server
    if (command.includes('stop') || command.includes('halt') || command.includes('silence')) {
        stopSpeech();
        speakText('Stopped');
        return true;
    }
    
    if (command.includes('pause')) {
        pauseSpeech();
        speakText('Paused');
        return true;
    }
    
    if (command.includes('resume') || command.includes('continue')) {
        resumeSpeech();
        speakText('Resumed');
        return true;
    }
    
    if (command.includes('repeat') || command.includes('say that again')) {
        repeatLastSpeech();
        return true;
    }
    
    if (command.includes('faster') || command.includes('speed up')) {
        currentSpeed = Math.min(2.0, currentSpeed + 0.2);
        updateSpeedDisplay();
        speakText(`Speed increased to ${currentSpeed.toFixed(1)} times`);
        return true;
    }
    
    if (command.includes('slower') || command.includes('slow down')) {
        currentSpeed = Math.max(0.5, currentSpeed - 0.2);
        updateSpeedDisplay();
        speakText(`Speed decreased to ${currentSpeed.toFixed(1)} times`);
        return true;
    }
    
    if (command.includes('help')) {
        showHelp();
        return true;
    }
    
    return false;
}

function updateSpeedDisplay() {
    document.getElementById('speedSlider').value = currentSpeed;
    document.getElementById('speedValue').textContent = currentSpeed.toFixed(1) + 'x';
    if (audioPlayer) {
        audioPlayer.playbackRate = currentSpeed;
    }
}

function showHelp() {
    const helpText = `Available commands: 
        • Read summary - reads the document summary
        • Read section [name] - reads a specific section
        • Summarize - generates a summary
        • Take note - saves a note
        • Add bookmark - bookmarks current section  
        • Generate quiz - creates a quiz
        • Speed up / Slow down - adjusts reading speed
        • Pause / Resume / Stop - controls playback
        • Repeat - repeats last spoken text`;
    
    speakText('Here are the available commands');
    setTimeout(() => {
        speakText(helpText);
    }, 1500);
    
    // Also display in UI
    const result = document.getElementById('commandResult');
    result.innerHTML = '<strong>Help:</strong><br>' + helpText.replace(/•/g, '<br>•');
}

// ==================== ENHANCED TEXT-TO-SPEECH WITH CHUNKING ====================

function speakText(text, isChunk = false) {
    if (!text || text.length < 2) return;
    
    // Stop any current speech
    if (!isChunk && window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        speechQueue = [];
    }
    
    // Split long text into chunks
    const chunks = splitIntoChunks(text);
    
    if (chunks.length > 1) {
        // Show speech controls for long text
        document.getElementById('speech-controls').style.display = 'flex';
        
        // Queue all chunks
        chunks.forEach((chunk, index) => {
            speechQueue.push({
                text: chunk,
                isLast: index === chunks.length - 1
            });
        });
        
        // Start processing queue
        processSpeechQueue();
    } else {
        // Short text - speak directly
        speakChunk(text, true);
    }
}

function splitIntoChunks(text) {
    // Split by sentences first
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    const chunks = [];
    let currentChunk = '';
    
    for (const sentence of sentences) {
        if ((currentChunk + sentence).length > MAX_CHUNK_LENGTH && currentChunk.length > 0) {
            chunks.push(currentChunk.trim());
            currentChunk = sentence;
        } else {
            currentChunk += ' ' + sentence;
        }
    }
    
    if (currentChunk.trim().length > 0) {
        chunks.push(currentChunk.trim());
    }
    
    return chunks;
}

function processSpeechQueue() {
    if (speechQueue.length === 0 || isSpeaking) {
        return;
    }
    
    const next = speechQueue.shift();
    speakChunk(next.text, next.isLast);
}

function speakChunk(text, isLast = true) {
    if (!window.speechSynthesis) return;
    
    isSpeaking = true;
    
    const utterance = new SpeechSynthesisUtterance(text);
    currentUtterance = utterance;
    
    // Apply voice settings
    utterance.rate = currentSpeed;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    utterance.lang = 'en-US';
    
    // Try to get a good voice
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => 
        voice.lang.includes('en') && 
        (voice.name.includes('Google') || voice.name.includes('Natural') || voice.name.includes('Samantha'))
    );
    
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }
    
    utterance.onstart = () => {
        document.getElementById('speech-controls').style.display = 'flex';
    };
    
    utterance.onend = () => {
        isSpeaking = false;
        currentUtterance = null;
        
        if (!isLast) {
            // Small pause between chunks
            setTimeout(() => {
                processSpeechQueue();
            }, 300);
        } else {
            // Hide controls after a delay when done
            setTimeout(() => {
                if (!isSpeaking && speechQueue.length === 0) {
                    document.getElementById('speech-controls').style.display = 'none';
                }
            }, 3000);
        }
    };
    
    utterance.onerror = (event) => {
        console.error('Speech error:', event);
        isSpeaking = false;
        currentUtterance = null;
        processSpeechQueue(); // Try next chunk
    };
    
    window.speechSynthesis.speak(utterance);
}

function pauseSpeech() {
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
        window.speechSynthesis.pause();
        document.getElementById('speech-pause').style.opacity = '0.5';
    }
}

function resumeSpeech() {
    if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
        document.getElementById('speech-pause').style.opacity = '1';
    } else if (speechQueue.length > 0 && !isSpeaking) {
        processSpeechQueue();
    }
}

function stopSpeech() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    speechQueue = [];
    isSpeaking = false;
    currentUtterance = null;
    document.getElementById('speech-controls').style.display = 'none';
}

function repeatLastSpeech() {
    // Get the last spoken text from the command result
    const lastResult = document.getElementById('commandResult').innerText;
    const match = lastResult.match(/System:(.+?)(?=You said:|$)/s);
    
    if (match && match[1]) {
        speakText(match[1].trim());
    } else {
        speakText('No previous speech to repeat');
    }
}

// ==================== COMMAND RESPONSE HANDLING ====================

async function handleCommandResponse(data, originalCommand) {
    let responseMessage = '';
    let textToSpeak = '';
    
    switch (data.intent) {
        case 'read_section':
            if (data.content) {
                displayContent(data.content);
                textToSpeak = data.content;
                responseMessage = 'Reading section';
            } else if (data.audio_url) {
                playAudioFromUrl(data.audio_url);
                responseMessage = 'Playing section audio';
            }
            break;
            
        case 'summarize':
            if (data.summary) {
                displayContent(data.summary);
                textToSpeak = data.summary;
                responseMessage = 'Summary generated';
            }
            break;
            
        case 'bookmark':
            responseMessage = data.message || 'Bookmark added';
            loadBookmarks();
            textToSpeak = responseMessage;
            break;
            
        case 'take_note':
            responseMessage = data.message || 'Note saved';
            loadNotes();
            textToSpeak = responseMessage;
            break;
            
        case 'generate_quiz':
            if (data.quiz) {
                displayQuiz(data.quiz);
                responseMessage = 'Quiz generated with 5 questions';
                textToSpeak = responseMessage;
            }
            break;
            
        case 'chat':
            if (data.answer) {
                addChatMessage(data.answer, 'assistant');
                textToSpeak = data.answer;
                responseMessage = '';
            }
            break;
    }
    
    // Speak the content or response
    if (textToSpeak) {
        speakText(textToSpeak);
    }
    
    // Update command result
    if (responseMessage) {
        document.getElementById('commandResult').innerHTML += `<br><strong>System:</strong> ${responseMessage}`;
    }
}

// ==================== DOCUMENT HANDLING ====================

async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    document.getElementById('fileName').textContent = file.name;
    
    const formData = new FormData();
    formData.append('file', file);
    
    showLoading('Uploading document...');
    speakText('Uploading document');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            await handleDocumentUpload(data);
            speakText('Document uploaded successfully');
        } else {
            showError(data.error || 'Upload failed');
            speakText('Upload failed');
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        showError('Failed to upload file');
        speakText('Upload failed');
    } finally {
        hideLoading();
    }
}

async function handleUrlSubmit() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }
    
    showLoading('Loading document from URL...');
    speakText('Loading document from URL');
    
    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success) {
            await handleDocumentUpload(data);
            speakText('Document loaded successfully');
        } else {
            showError(data.error || 'Failed to load URL');
            speakText('Failed to load document');
        }
    } catch (error) {
        console.error('Error loading URL:', error);
        showError('Failed to load URL');
        speakText('Connection error');
    } finally {
        hideLoading();
    }
}

async function handleDocumentUpload(data) {
    currentDocumentId = data.document_id;
    
    // Display overview
    document.getElementById('overviewSection').style.display = 'block';
    document.getElementById('overviewText').textContent = data.overview;
    
    // Store audio URL for overview
    if (data.audio_url) {
        document.getElementById('playOverviewBtn').dataset.audioUrl = data.audio_url;
    }
    
    // Display sections
    if (data.sections) {
        displaySections(data.sections);
    }
    
    // Show success message
    showSuccess('Document loaded successfully!');
    
    // Welcome message
    const welcomeMessage = `${data.filename} loaded. You can say "read summary" or "read section" followed by a section name.`;
    speakText(welcomeMessage);
}

function displaySections(sections) {
    document.getElementById('sectionsSection').style.display = 'block';
    const sectionsList = document.getElementById('sectionsList');
    sectionsList.innerHTML = '';
    
    Object.keys(sections).forEach(section => {
        const sectionItem = document.createElement('div');
        sectionItem.className = 'section-item';
        sectionItem.textContent = section;
        sectionItem.addEventListener('click', () => {
            processVoiceCommand(`read section ${section}`);
        });
        sectionsList.appendChild(sectionItem);
    });
}

function displayContent(content) {
    const display = document.getElementById('contentDisplay');
    display.innerHTML = `<div class="content-text">${content.replace(/\n/g, '<br>')}</div>`;
    
    // Highlight the content briefly
    display.style.backgroundColor = '#fff3cd';
    setTimeout(() => {
        display.style.backgroundColor = '';
    }, 1000);
}

// ==================== AUDIO PLAYER ====================

function setupAudioPlayer() {
    audioPlayer.addEventListener('play', () => {
        document.getElementById('playBtn').style.opacity = '0.5';
        document.getElementById('pauseBtn').style.opacity = '1';
    });
    
    audioPlayer.addEventListener('pause', () => {
        document.getElementById('playBtn').style.opacity = '1';
        document.getElementById('pauseBtn').style.opacity = '0.5';
    });
    
    audioPlayer.addEventListener('ended', () => {
        document.getElementById('playBtn').style.opacity = '1';
        document.getElementById('pauseBtn').style.opacity = '0.5';
        speakText('Playback finished');
    });
    
    audioPlayer.addEventListener('error', (e) => {
        console.error('Audio error:', e);
        showError('Failed to play audio');
    });
}

function playAudioFromUrl(url) {
    if (!url) return;
    
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    
    audioPlayer.src = fullUrl;
    audioPlayer.playbackRate = currentSpeed;
    audioPlayer.play().catch(error => {
        console.error('Error playing audio:', error);
        showError('Failed to play audio');
    });
}

function playAudio() {
    if (audioPlayer.src) {
        audioPlayer.play();
    }
}

function pauseAudio() {
    audioPlayer.pause();
}

function stopAudio() {
    audioPlayer.pause();
    audioPlayer.currentTime = 0;
}

function repeatAudio() {
    if (audioPlayer.src) {
        audioPlayer.currentTime = 0;
        audioPlayer.play();
    }
}

// ==================== NOTES AND BOOKMARKS ====================

async function loadNotes() {
    if (!currentDocumentId) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/notes/${currentDocumentId}`);
        const data = await response.json();
        
        if (data.success) {
            displayNotes(data.notes);
        }
    } catch (error) {
        console.error('Error loading notes:', error);
    }
}

async function loadBookmarks() {
    if (!currentDocumentId) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/bookmarks/${currentDocumentId}`);
        const data = await response.json();
        
        if (data.success) {
            displayBookmarks(data.bookmarks);
        }
    } catch (error) {
        console.error('Error loading bookmarks:', error);
    }
}

function displayNotes(notes) {
    const list = document.getElementById('notesList');
    list.innerHTML = '';
    
    if (!notes || notes.length === 0) {
        list.innerHTML = '<li>No notes yet</li>';
        return;
    }
    
    notes.forEach(note => {
        const li = document.createElement('li');
        li.innerHTML = `
            <strong>${new Date(note.created_at).toLocaleString()}</strong><br>
            ${note.note}
        `;
        list.appendChild(li);
    });
}

function displayBookmarks(bookmarks) {
    const list = document.getElementById('bookmarksList');
    list.innerHTML = '';
    
    if (!bookmarks || bookmarks.length === 0) {
        list.innerHTML = '<li>No bookmarks yet</li>';
        return;
    }
    
    bookmarks.forEach(bookmark => {
        const li = document.createElement('li');
        li.innerHTML = `
            <strong>Section: ${bookmark.section}</strong><br>
            <small>${new Date(bookmark.created_at).toLocaleString()}</small>
        `;
        list.appendChild(li);
    });
}

// ==================== QUIZ ====================

async function generateQuiz() {
    if (!currentDocumentId) {
        showError('Please upload a document first');
        speakText('Please upload a document first');
        return;
    }
    
    showLoading('Generating quiz...');
    speakText('Generating quiz');
    
    try {
        const response = await fetch(`${API_BASE_URL}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: 'generate quiz',
                document_id: currentDocumentId
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.quiz) {
            displayQuiz(data.quiz);
            document.getElementById('quizSection').style.display = 'block';
            speakText('Quiz generated with 5 questions');
        } else {
            showError('Failed to generate quiz');
            speakText('Quiz generation failed');
        }
    } catch (error) {
        console.error('Error generating quiz:', error);
        showError('Failed to generate quiz');
        speakText('Connection error');
    } finally {
        hideLoading();
    }
}

function displayQuiz(quiz) {
    const container = document.getElementById('quizContainer');
    container.innerHTML = '';
    
    quiz.questions.forEach((q, index) => {
        const questionDiv = document.createElement('div');
        questionDiv.className = 'question-item';
        questionDiv.innerHTML = `
            <p><strong>Question ${index + 1}:</strong> ${q.question}</p>
            <div class="options">
                ${q.options.map((opt, i) => `
                    <label class="option">
                        <input type="radio" name="q${index}" value="${opt}">
                        ${opt}
                    </label>
                `).join('')}
            </div>
            <button class="secondary-btn check-answer" data-q="${index}" data-answer="${q.correct_answer}">
                Check Answer
            </button>
            <div class="answer-feedback" id="feedback${index}"></div>
        `;
        
        container.appendChild(questionDiv);
    });
    
    // Add check answer listeners
    document.querySelectorAll('.check-answer').forEach(btn => {
        btn.addEventListener('click', checkAnswer);
    });
}

function checkAnswer(event) {
    const btn = event.target;
    const questionIndex = btn.dataset.q;
    const correctAnswer = btn.dataset.answer;
    const selected = document.querySelector(`input[name="q${questionIndex}"]:checked`);
    const feedback = document.getElementById(`feedback${questionIndex}`);
    
    if (!selected) {
        feedback.innerHTML = '<span style="color: orange;">⚠️ Please select an answer</span>';
        return;
    }
    
    if (selected.value === correctAnswer) {
        feedback.innerHTML = '<span style="color: green;">✅ Correct!</span>';
        speakText('Correct answer');
    } else {
        feedback.innerHTML = `<span style="color: red;">❌ Incorrect. The correct answer is: ${correctAnswer}</span>`;
        speakText('Incorrect answer');
    }
}

// ==================== CHAT ====================

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    if (!currentDocumentId) {
        showError('Please upload a document first');
        speakText('Please upload a document first');
        return;
    }
    
    // Add user message
    addChatMessage(message, 'user');
    input.value = '';
    
    showLoading('Thinking...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: message,
                document_id: currentDocumentId
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.answer) {
            addChatMessage(data.answer, 'assistant');
            speakText(data.answer);
        } else {
            addChatMessage('Sorry, I couldn\'t process that question.', 'assistant');
            speakText('Sorry, I could not answer that question');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        addChatMessage('Error connecting to server', 'assistant');
        speakText('Connection error');
    } finally {
        hideLoading();
    }
}

function addChatMessage(message, sender) {
    const history = document.getElementById('chatHistory');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    messageDiv.textContent = message;
    history.appendChild(messageDiv);
    history.scrollTop = history.scrollHeight;
}

// ==================== EXPORT ====================

async function exportData() {
    if (!currentDocumentId) {
        showError('No document loaded');
        speakText('No document to export');
        return;
    }
    
    try {
        window.open(`${API_BASE_URL}/export/${currentDocumentId}`, '_blank');
        speakText('Exporting document');
    } catch (error) {
        console.error('Error exporting data:', error);
        showError('Failed to export data');
    }
}

// ==================== ACCESSIBILITY FUNCTIONS ====================

function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    savePreference('darkMode', document.body.classList.contains('dark-mode'));
    speakText(document.body.classList.contains('dark-mode') ? 'Dark mode enabled' : 'Light mode enabled');
}

function toggleHighContrast() {
    document.body.classList.toggle('high-contrast');
    savePreference('highContrast', document.body.classList.contains('high-contrast'));
    speakText(document.body.classList.contains('high-contrast') ? 'High contrast enabled' : 'Normal contrast');
}

function increaseFont() {
    document.body.classList.add('large-font');
    savePreference('largeFont', true);
    speakText('Font size increased');
}

function decreaseFont() {
    document.body.classList.remove('large-font');
    savePreference('largeFont', false);
    speakText('Font size decreased');
}

function switchTab(event) {
    const tab = event.target.dataset.tab;
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tab + 'Tab').classList.add('active');
    
    // Load data for the tab
    if (tab === 'notes') {
        loadNotes();
    } else if (tab === 'bookmarks') {
        loadBookmarks();
    }
}

// ==================== UTILITY FUNCTIONS ====================

function loadPreferences() {
    const prefs = JSON.parse(localStorage.getItem('voicenav_prefs') || '{}');
    
    if (prefs.darkMode) document.body.classList.add('dark-mode');
    if (prefs.highContrast) document.body.classList.add('high-contrast');
    if (prefs.largeFont) document.body.classList.add('large-font');
    if (prefs.speed) {
        currentSpeed = prefs.speed;
        updateSpeedDisplay();
    }
}

// Chat functions
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    
    if (!question) return;
    if (!currentDocId) {
        showToast('Please upload a document first', 'error');
        return;
    }
    
    // Add user message to chat
    addChatMessage(question, 'user');
    input.value = '';
    
    // Show loading
    commandBox.innerHTML = '💭 Thinking...';
    
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                document_id: currentDocId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            addChatMessage(data.answer, 'bot', data.confidence);
            commandBox.innerHTML = '✅ Question answered';
            
            // Speak the answer if it's short enough
            if (data.answer.length < 200) {
                speakText(data.answer);
            }
        } else {
            showToast(data.error || 'Failed to get answer', 'error');
        }
    } catch (error) {
        console.error('Chat error:', error);
        showToast('Failed to connect', 'error');
    }
}

function startVoiceChat() {
    if (!currentDocId) {
        showToast('Please upload a document first', 'error');
        return;
    }
    
    // Use existing speech recognition but set context
    if (recognition) {
        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            
            if (event.results[0].isFinal) {
                document.getElementById('chatInput').value = transcript;
                sendChatMessage();
            }
        };
        toggleRecording();
    }
}

function addChatMessage(text, sender, confidence = 1.0) {
    const history = document.getElementById('chatHistory');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;
    
    let confidenceClass = '';
    let confidenceText = '';
    
    if (sender === 'bot' && confidence < 1.0) {
        if (confidence > 0.7) confidenceClass = 'high-confidence';
        else if (confidence > 0.3) confidenceClass = 'med-confidence';
        else confidenceClass = 'low-confidence';
        confidenceText = `<span class="confidence-badge ${confidenceClass}">${Math.round(confidence*100)}%</span>`;
    }
    
    messageDiv.innerHTML = `
        <div>${text} ${confidenceText}</div>
        <div class="message-time">${time}</div>
    `;
    
    history.appendChild(messageDiv);
    history.scrollTop = history.scrollHeight;
}

async function clearChat() {
    if (!currentDocId) return;
    
    try {
        const response = await fetch(`${API_BASE}/chat/clear/${currentDocId}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('chatHistory').innerHTML = `
                <div style="text-align: center; color: #999; padding: 20px;">
                    Chat cleared. Ask a new question!
                </div>
            `;
            showToast('Chat cleared', 'success');
        }
    } catch (error) {
        console.error('Error clearing chat:', error);
    }
}

function savePreference(key, value) {
    const prefs = JSON.parse(localStorage.getItem('voicenav_prefs') || '{}');
    prefs[key] = value;
    
    // Save current speed
    prefs.speed = currentSpeed;
    
    localStorage.setItem('voicenav_prefs', JSON.stringify(prefs));
}

function showLoading(message) {
    let loader = document.getElementById('loadingIndicator');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'loadingIndicator';
        loader.className = 'loading-indicator';
        document.body.appendChild(loader);
    }
    loader.textContent = message || 'Loading...';
    loader.style.display = 'block';
}

function hideLoading() {
    const loader = document.getElementById('loadingIndicator');
    if (loader) {
        loader.style.display = 'none';
    }
}

function showError(message) {
    console.error('Error:', message);
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'toast error';
    toast.textContent = '❌ ' + message;
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        right: 20px;
        background: #f44336;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        z-index: 2000;
        animation: slideIn 0.3s;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function showSuccess(message) {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'toast success';
    toast.textContent = '✅ ' + message;
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        right: 20px;
        background: #4CAF50;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        z-index: 2000;
        animation: slideIn 0.3s;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .voice-status {
        position: fixed;
        bottom: 80px;
        right: 20px;
        padding: 5px 10px;
        background: rgba(0,0,0,0.7);
        color: #f44336;
        border-radius: 20px;
        font-size: 12px;
        z-index: 1000;
        transition: all 0.3s;
    }
    
    .speech-controls {
        position: fixed;
        bottom: 120px;
        right: 20px;
        display: none;
        gap: 5px;
        z-index: 1000;
        background: rgba(0,0,0,0.8);
        padding: 10px;
        border-radius: 50px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    
    .speech-control-btn {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        border: none;
        background: #333;
        color: white;
        font-size: 18px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .speech-control-btn:hover {
        background: #555;
        transform: scale(1.1);
    }
    
    .speech-control-btn:active {
        transform: scale(0.95);
    }
`;

document.head.appendChild(style);