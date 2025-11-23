import { useMemo } from 'react'
import { useAgent } from '../../../contexts/agent/AgentContext'
import { AgentProfileType, AgentProfileInfo } from '@aiNagisa/core'
import { ProfileSelectorStateHookReturn } from '../types'

/**
 * Custom hook for managing AgentProfileSelector state.
 * 
 * Handles data source determination (context vs props) and provides
 * computed state values for the selector component. Follows aiNagisa's
 * hook architecture pattern with clear return type interface.
 * 
 * Args:
 *     useContext: Whether to use AgentContext for data
 *     propCurrentProfile: Profile passed via props
 *     propAvailableProfiles: Available profiles passed via props
 *     propIsLoading: Loading state passed via props
 * 
 * Returns:
 *     ProfileSelectorStateHookReturn: Complete state object with computed values:
 *         - currentProfile: AgentProfileType | undefined - Active profile
 *         - availableProfiles: AgentProfileInfo[] - All available profiles
 *         - isLoading: boolean - Loading state indicator
 *         - currentProfileInfo: AgentProfileInfo | undefined - Current profile details
 *         - error: string | null - Error message if any
 * 
 * TypeScript Learning Points:
 * - Union types for flexible data sources (context | props)
 * - Optional parameters with default values
 * - Computed values with useMemo for performance
 * - Clear return type interface for hook contracts
 */
export const useProfileSelectorState = (
  useContext: boolean = false,
  propCurrentProfile?: AgentProfileType,
  propAvailableProfiles?: AgentProfileInfo[],
  propIsLoading: boolean = false
): ProfileSelectorStateHookReturn => {
  // Context integration when needed
  const contextAgent = useAgent()
  
  // Determine data source (context vs props)
  const currentProfile = useContext ? contextAgent.currentProfile : propCurrentProfile
  const availableProfiles = useContext ? contextAgent.availableProfiles : (propAvailableProfiles || [])
  const isLoading = useContext ? contextAgent.isProfileLoading : propIsLoading
  
  // Computed values with memoization for performance
  const currentProfileInfo = useMemo(() => {
    if (!currentProfile || !availableProfiles.length) return undefined
    return availableProfiles.find(p => p.profile_type === currentProfile)
  }, [currentProfile, availableProfiles])
  
  const error = useMemo(() => {
    if (!currentProfile && availableProfiles.length > 0) {
      return 'No current profile selected'
    }
    if (currentProfile && !currentProfileInfo) {
      return 'Current profile not found in available profiles'
    }
    return null
  }, [currentProfile, availableProfiles.length, currentProfileInfo])
  
  return {
    currentProfile,
    availableProfiles,
    isLoading,
    currentProfileInfo,
    error
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Hook Parameter Flexibility:
 *    Optional parameters with defaults enable multiple usage patterns
 * 
 * 2. Conditional Data Sources:
 *    Ternary operators select between context and props data
 * 
 * 3. Performance Optimization:
 *    useMemo prevents unnecessary recalculations of derived state
 * 
 * 4. Type Safety:
 *    All return values match the defined interface contract
 * 
 * 5. Error Handling Strategy:
 *    Comprehensive error detection with user-friendly messages
 * 
 * Benefits of This Pattern:
 * - Single source of truth for component state logic
 * - Easy to test in isolation
 * - Supports both controlled and uncontrolled usage patterns
 * - Clear separation between data fetching and UI logic
 * - Performance-optimized with memoization
 */