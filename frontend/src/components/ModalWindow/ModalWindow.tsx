import type { FC } from 'react';
import { X } from 'lucide-react';
import './ModalWindow.css';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    icon?: string;
    dismissible?: boolean;
}

export const ModalWindow: FC<ModalProps> = ({isOpen, onClose, title, children, icon, dismissible = true}: ModalProps) => {
    if (!isOpen) {
        return null;
    }

    return (
        <div className="modal-overlay">
            <div className="modal-container">
                <div className="modal-header">
                    <div className="modal-title-container">
                        {icon && <img src={icon} alt={title} className="modal-header-icon" />}
                        <h2 className="modal-title">
                            {title.includes('\n') ? title : title.replace(' ', '\n')}
                        </h2>
                    </div>
                    {dismissible && (
                    <button
                        onClick={onClose}
                        className="modal-close-button"
                        aria-label="Close"
                    >
                        <X size={16} strokeWidth={2} />
                    </button>
                    )}
                </div>
                <div className="modal-content">
                    {children}
                </div>
            </div>
        </div>
    );
}