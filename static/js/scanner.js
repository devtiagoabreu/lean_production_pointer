let html5QrcodeScanner = null;
let currentCameraId = null;

function onScanSuccess(decodedText, decodedResult) {
    // Parar scanner temporariamente
    if (html5QrcodeScanner) {
        html5QrcodeScanner.pause();
    }
    
    // Mostrar mensagem de sucesso
    const statusElement = document.getElementById('status-message');
    statusElement.innerHTML = `<i class="fas fa-check-circle"></i> QR Code lido! Validando...`;
    statusElement.style.color = '#28a745';
    
    // Validar QR Code
    validateQRCode(decodedText);
}

function onScanFailure(error) {
    // Apenas logar erros, não mostrar para o usuário
    console.log(`Erro de scanner: ${error}`);
}

function initScanner() {
    // Verificar se já existe um scanner
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear();
    }
    
    // Configurar scanner
    html5QrcodeScanner = new Html5QrcodeScanner(
        "qr-reader",
        { 
            fps: 10,
            qrbox: { width: 250, height: 250 },
            rememberLastUsedCamera: true,
            showTorchButtonIfSupported: true
        },
        false
    );
    
    // Renderizar scanner
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

async function switchCamera() {
    try {
        const devices = await Html5Qrcode.getCameras();
        if (devices && devices.length > 1) {
            if (html5QrcodeScanner) {
                html5QrcodeScanner.clear();
            }
            
            // Encontrar próximo dispositivo de câmera
            const currentIndex = currentCameraId 
                ? devices.findIndex(d => d.id === currentCameraId)
                : -1;
            
            const nextIndex = (currentIndex + 1) % devices.length;
            const nextCamera = devices[nextIndex];
            
            currentCameraId = nextCamera.id;
            
            // Reiniciar scanner com nova câmera
            html5QrcodeScanner = new Html5QrcodeScanner(
                "qr-reader",
                { 
                    fps: 10,
                    qrbox: { width: 250, height: 250 },
                    videoConstraints: {
                        deviceId: { exact: nextCamera.id }
                    }
                },
                false
            );
            
            html5QrcodeScanner.render(onScanSuccess, onScanFailure);
            
            // Mostrar mensagem
            const statusElement = document.getElementById('status-message');
            statusElement.innerHTML = `<i class="fas fa-camera"></i> Câmera: ${nextCamera.label}`;
            statusElement.style.color = '#007bff';
        }
    } catch (error) {
        console.error('Erro ao alternar câmera:', error);
    }
}

async function validateQRCode(qrCode) {
    try {
        const response = await fetch('/api/validate_qr', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ qr_code: qrCode })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const statusElement = document.getElementById('status-message');
            statusElement.innerHTML = `<i class="fas fa-check-circle"></i> Validado! Redirecionando...`;
            statusElement.style.color = '#28a745';
            
            // Pequeno delay para mostrar mensagem
            setTimeout(() => {
                window.location.href = result.redirect;
            }, 1500);
        } else {
            const statusElement = document.getElementById('status-message');
            statusElement.innerHTML = `<i class="fas fa-times-circle"></i> ${result.message}`;
            statusElement.style.color = '#dc3545';
            
            // Reiniciar scanner após 3 segundos
            setTimeout(() => {
                statusElement.innerHTML = `<i class="fas fa-hourglass-half"></i> Aguardando leitura do QR Code...`;
                statusElement.style.color = '';
                if (html5QrcodeScanner) {
                    html5QrcodeScanner.resume();
                }
            }, 3000);
        }
    } catch (error) {
        const statusElement = document.getElementById('status-message');
        statusElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erro de conexão`;
        statusElement.style.color = '#dc3545';
        
        setTimeout(() => {
            statusElement.innerHTML = `<i class="fas fa-hourglass-half"></i> Aguardando leitura do QR Code...`;
            statusElement.style.color = '';
            if (html5QrcodeScanner) {
                html5QrcodeScanner.resume();
            }
        }, 3000);
    }
}

function validateManualCode() {
    const manualCode = document.getElementById('manual-code').value.trim();
    
    if (!manualCode) {
        alert('Digite um código!');
        return;
    }
    
    const statusElement = document.getElementById('status-message');
    statusElement.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Validando código...`;
    
    validateQRCode(manualCode);
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    initScanner();
    
    // Adicionar listener para input manual
    const manualInput = document.getElementById('manual-code');
    if (manualInput) {
        manualInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                validateManualCode();
            }
        });
    }
});