import React from 'react'
import { MessageRole } from '@aiNagisa/core'

/**
 * Avatar tooltip utility functions.
 *
 * Provides helper functions for showing and hiding avatar tooltips with
 * role-specific information and positioning logic.
 */

/**
 * Show avatar tooltip on hover.
 *
 * Creates and positions a tooltip element with role information.
 *
 * Args:
 *     e: Mouse event from avatar hover
 *     role: Message role type for content determination
 */
export const showAvatarTooltip = (e: React.MouseEvent<HTMLImageElement>, role: MessageRole) => {
  const tooltip = document.createElement('div')
  tooltip.className = 'avatar-tooltip'

  if (role === 'user') {
    tooltip.textContent = 'User\nName：yusong\nIntroduction： developer of aiNagisa.'
  } else {
    tooltip.textContent = 'Toyoura Nagisa\nPersonality: Energetic, cute, clingy\nHobbies: Chatting with you, being adorable\nBio: Nagisa is your AI virtual companion who loves to keep you company and interact with you!'
  }

  document.body.appendChild(tooltip)
  const rect = e.currentTarget.getBoundingClientRect()

  if (role === 'user') {
    tooltip.style.left = `${rect.left - tooltip.offsetWidth - 10}px`
    tooltip.style.top = `${rect.top - 10}px`
  } else {
    tooltip.style.left = `${rect.right + 10}px`
    tooltip.style.top = `${rect.top - 10}px`
  }
}

/**
 * Hide avatar tooltip on mouse leave.
 * 
 * Removes any existing tooltip from the DOM.
 */
export const hideAvatarTooltip = () => {
  const tooltip = document.querySelector('.avatar-tooltip')
  if (tooltip) tooltip.remove()
}

// Default export component (not used but maintains consistency)
const AvatarTooltip: React.FC = () => null
export default AvatarTooltip