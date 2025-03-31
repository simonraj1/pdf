// PDF to Questions UI JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // File input preview
    const fileInput = document.getElementById('pdf_file');
    const filePreview = document.getElementById('file-preview');
    const fileName = document.getElementById('file-name');
    
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const file = this.files[0];
                fileName.textContent = file.name;
                filePreview.classList.remove('d-none');
                
                // Add file size information
                const fileSizeKB = Math.round(file.size / 1024);
                let fileSizeText = fileSizeKB + ' KB';
                if (fileSizeKB > 1024) {
                    const fileSizeMB = (fileSizeKB / 1024).toFixed(2);
                    fileSizeText = fileSizeMB + ' MB';
                }
                
                // Create and append file size element
                const fileSizeElement = document.createElement('small');
                fileSizeElement.className = 'text-muted ms-2';
                fileSizeElement.textContent = `(${fileSizeText})`;
                
                // Remove any existing file size element
                const existingFileSize = fileName.parentNode.querySelector('small');
                if (existingFileSize) {
                    existingFileSize.remove();
                }
                
                fileName.parentNode.appendChild(fileSizeElement);
            } else {
                filePreview.classList.add('d-none');
            }
        });
    }
    
    // Form validation
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(event) {
            let isValid = true;
            
            // Validate file input
            if (fileInput && fileInput.files.length === 0) {
                showValidationError(fileInput, 'Please select a PDF file');
                isValid = false;
            }
            
            // Validate start page
            const startPageInput = document.getElementById('start_page');
            if (startPageInput) {
                const startPage = parseInt(startPageInput.value);
                if (isNaN(startPage) || startPage < 1) {
                    showValidationError(startPageInput, 'Start page must be at least 1');
                    isValid = false;
                }
            }
            
            // Validate max pages
            const maxPagesInput = document.getElementById('max_pages');
            if (maxPagesInput && maxPagesInput.value) {
                const maxPages = parseInt(maxPagesInput.value);
                if (isNaN(maxPages) || maxPages < 1) {
                    showValidationError(maxPagesInput, 'Max pages must be at least 1');
                    isValid = false;
                }
            }
            
            // Validate delay
            const delayInput = document.getElementById('delay');
            if (delayInput) {
                const delay = parseInt(delayInput.value);
                if (isNaN(delay) || delay < 1) {
                    showValidationError(delayInput, 'Delay must be at least 1 second');
                    isValid = false;
                }
            }
            
            if (!isValid) {
                event.preventDefault();
                return false;
            }
            
            // Show loading state
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
            }
            
            // Add a loading overlay
            const loadingOverlay = document.createElement('div');
            loadingOverlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center';
            loadingOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
            loadingOverlay.style.zIndex = '9999';
            
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'spinner-border text-light';
            loadingSpinner.style.width = '3rem';
            loadingSpinner.style.height = '3rem';
            loadingSpinner.setAttribute('role', 'status');
            
            const loadingText = document.createElement('span');
            loadingText.className = 'text-light ms-3 fs-4';
            loadingText.textContent = 'Uploading PDF...';
            
            const spinnerContainer = document.createElement('div');
            spinnerContainer.className = 'd-flex align-items-center bg-dark p-4 rounded';
            spinnerContainer.appendChild(loadingSpinner);
            spinnerContainer.appendChild(loadingText);
            
            loadingOverlay.appendChild(spinnerContainer);
            document.body.appendChild(loadingOverlay);
            
            return true;
        });
    }
    
    // Input validation on blur
    const validateOnBlur = function(input, validationFn) {
        if (input) {
            input.addEventListener('blur', function() {
                const errorMessage = validationFn(this.value);
                if (errorMessage) {
                    showValidationError(this, errorMessage);
                } else {
                    clearValidationError(this);
                }
            });
            
            // Clear error on focus
            input.addEventListener('focus', function() {
                clearValidationError(this);
            });
        }
    };
    
    // Validate start page
    validateOnBlur(
        document.getElementById('start_page'),
        function(value) {
            const startPage = parseInt(value);
            return (isNaN(startPage) || startPage < 1) ? 'Start page must be at least 1' : null;
        }
    );
    
    // Validate max pages
    validateOnBlur(
        document.getElementById('max_pages'),
        function(value) {
            if (!value.trim()) return null; // Optional field
            const maxPages = parseInt(value);
            return (isNaN(maxPages) || maxPages < 1) ? 'Max pages must be at least 1' : null;
        }
    );
    
    // Validate delay
    validateOnBlur(
        document.getElementById('delay'),
        function(value) {
            const delay = parseInt(value);
            return (isNaN(delay) || delay < 1) ? 'Delay must be at least 1 second' : null;
        }
    );
    
    // Helper functions for validation
    function showValidationError(input, message) {
        clearValidationError(input);
        
        input.classList.add('is-invalid');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        
        input.parentNode.appendChild(errorDiv);
    }
    
    function clearValidationError(input) {
        input.classList.remove('is-invalid');
        
        const container = input.parentNode;
        const errorDiv = container.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    }
}); 