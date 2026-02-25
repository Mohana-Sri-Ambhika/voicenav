// Audio Controls Manager
class AudioControlsManager {
    constructor() {
        this.audioContext = null;
        this.analyser = null;
        this.source = null;
        this.isInitialized = false;
    }
    
    async initialize() {
        if (this.isInitialized) return;
        
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.isInitialized = true;
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
        }
    }
    
    connectAudio(audioElement) {
        if (!this.isInitialized) return;
        
        try {
            this.source = this.audioContext.createMediaElementSource(audioElement);
            this.source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);
        } catch (error) {
            console.error('Failed to connect audio:', error);
        }
    }
    
    getAudioData() {
        if (!this.analyser) return null;
        
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);
        return dataArray;
    }
    
    async resume() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
    }
}

// Initialize audio controls when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.audioControls = new AudioControlsManager();
    window.audioControls.initialize();
});