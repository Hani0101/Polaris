import type { ReactNode } from 'react'
import { AlertCircle, Copy, Menu, MessageSquare, RotateCcw, Send, Square, Star, X } from 'lucide-react'

type IconButtonProps = {
  label: string
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'ghost' | 'primary'
  size?: 'md' | 'sm'
  type?: 'button' | 'submit'
}

export function IconButton({
  label,
  children,
  onClick,
  disabled,
  variant = 'ghost',
  size = 'md',
  type = 'button',
}: IconButtonProps) {
  return (
    <button
      type={type}
      className={`icon-btn icon-btn--${variant} icon-btn--${size}`}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

export function MenuIcon() {
  return <Menu size={24} strokeWidth={2} aria-hidden="true" />
}

export function CloseIcon() {
  return <X size={20} strokeWidth={2} aria-hidden="true" />
}

export function SendIcon() {
  return <Send size={20} strokeWidth={2} aria-hidden="true" />
}

export function StopIcon() {
  return <Square size={20} strokeWidth={2} aria-hidden="true" />
}

export function CopyIcon() {
  return <Copy size={20} strokeWidth={2} aria-hidden="true" />
}

export function RetryIcon() {
  return <RotateCcw size={20} strokeWidth={2} aria-hidden="true" />
}

export function AlertIcon() {
  return <AlertCircle size={16} strokeWidth={2} aria-hidden="true" />
}

export function EmptyIcon() {
  return <MessageSquare size={24} strokeWidth={2} aria-hidden="true" />
}

/** DS-GAP: Polaris star mark TBD (section 9), used Lucide Star */
export function PolarisStar({ pulse = false }: { pulse?: boolean }) {
  return (
    <Star
      className={pulse ? 'polaris-star is-pulse' : 'polaris-star'}
      size={20}
      strokeWidth={2}
      aria-hidden="true"
    />
  )
}

export function AlertBanner({
  children,
  action,
}: {
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="alert alert--error" role="alert">
      <AlertIcon />
      <div className="alert-body">
        <p>{children}</p>
        {action}
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string
  body: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <EmptyIcon />
      <h2 className="empty-state-title">{title}</h2>
      <p className="empty-state-body">{body}</p>
      {action}
    </div>
  )
}

export function ThinkingIndicator({ status }: { status: string }) {
  return (
    <p className="thinking" aria-live="polite">
      <PolarisStar pulse />
      <span>{status}</span>
    </p>
  )
}

export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="toast" role="status">
      <p>{message}</p>
      <IconButton label="Close" size="sm" onClick={onClose}>
        <CloseIcon />
      </IconButton>
    </div>
  )
}
