import React from 'react'
import { AgentProfileType } from '../../../types/agent'
import { ProfileIconProps } from '../types'

/**
 * SVG icon component for different agent profiles.
 * 
 * Renders scalable vector icons for each agent profile type using clean SVG
 * definitions. Provides consistent iconography across the application with
 * proper accessibility attributes.
 * 
 * Args:
 *     profile: AgentProfileType - The profile type to render icon for
 *     size: number - Icon size in pixels (default: 16)
 * 
 * Returns:
 *     JSX.Element | null: SVG icon element or null for unknown profiles
 * 
 * TypeScript Learning Points:
 * - Discriminated unions with switch statements
 * - Optional props with default values
 * - Return type unions (JSX.Element | null)
 * - Object spread for common props
 */
const ProfileIcon: React.FC<ProfileIconProps> = ({ profile, size = 16 }) => {
  const iconProps = {
    width: size,
    height: size,
    fill: "currentColor",
    viewBox: "0 0 16 16",
    "aria-hidden": true as const // Icons are decorative, screen readers use text labels
  }

  switch (profile) {
    case AgentProfileType.CODING:
      return (
        <svg {...iconProps} role="img" aria-label="Coding profile">
          <path d="M5.854 4.854a.5.5 0 1 0-.708-.708l-3.5 3.5a.5.5 0 0 0 0 .708l3.5 3.5a.5.5 0 0 0 .708-.708L2.707 8l3.147-3.146zm4.292 0a.5.5 0 0 1 .708-.708l3.5 3.5a.5.5 0 0 1 0 .708l-3.5 3.5a.5.5 0 0 1-.708-.708L13.293 8l-3.147-3.146z"/>
        </svg>
      )
      
    case AgentProfileType.LIFESTYLE:
      return (
        <svg {...iconProps} role="img" aria-label="Lifestyle profile">
          <path d="M3.612 15.443c-.386.198-.824-.149-.746-.592l.83-4.73L.173 6.765c-.329-.314-.158-.888.283-.95l4.898-.696L7.538.792c.197-.39.73-.39.927 0l2.184 4.327 4.898.696c.441.062.612.636.282.95l-3.522 3.356.83 4.73c.078.443-.36.79-.746.592L8 13.187l-4.389 2.256z"/>
        </svg>
      )
      
    case AgentProfileType.PFC:
      return (
        <svg {...iconProps} role="img" aria-label="PFC Expert profile">
          <circle cx="8" cy="8" r="1.5"/>
          <circle cx="4" cy="4" r="1"/>
          <circle cx="12" cy="4" r="1"/>
          <circle cx="4" cy="12" r="1"/>
          <circle cx="12" cy="12" r="1"/>
          <path d="M8 6.5v-2M8 9.5v2M6.5 8h-2M9.5 8h2M5.5 5.5L4 4M10.5 5.5L12 4M5.5 10.5L4 12M10.5 10.5L12 12" stroke="currentColor" fill="none" strokeWidth="0.5"/>
        </svg>
      )
      
    case AgentProfileType.GENERAL:
      return (
        <svg {...iconProps} role="img" aria-label="General profile">
          <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5ZM3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.58 26.58 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.933.933 0 0 1-.765.935c-.845.147-2.34.346-4.235.346-1.895 0-3.39-.2-4.235-.346A.933.933 0 0 1 3 9.219V8.062Zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a24.767 24.767 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25.286 25.286 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.07l-.754.785-.842-1.71a.25.25 0 0 0-.182-.119Z"/>
          <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2V1.866ZM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5Z"/>
        </svg>
      )
      
    case AgentProfileType.DISABLED:
      return (
        <svg {...iconProps} role="img" aria-label="Disabled profile">
          <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      )
      
    default:
      return null
  }
}

export default ProfileIcon

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Discriminated Union Switch:
 *    TypeScript narrows the profile type in each case branch
 * 
 * 2. Object Spread with Typing:
 *    iconProps spread maintains type safety for SVG attributes
 * 
 * 3. Default Parameters:
 *    size = 16 provides fallback while maintaining type inference
 * 
 * 4. Accessibility Attributes:
 *    aria-hidden and role for proper screen reader support
 * 
 * 5. Union Return Types:
 *    JSX.Element | null allows for conditional rendering
 * 
 * Benefits of This Component:
 * - Consistent iconography across the application
 * - Scalable vector graphics for crisp display
 * - Accessibility features built-in
 * - Type-safe profile icon mapping
 * - Performance optimized (no external image loading)
 */