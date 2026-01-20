import React from 'react';
import { Box, Text, type BoxProps } from 'ink';
import { theme, colors } from '../../colors.js';

export type PanelTone =
  | 'default'
  | 'muted'
  | 'accent'
  | 'primary'
  | 'info'
  | 'success'
  | 'warning'
  | 'error';

interface PanelSectionProps extends Omit<BoxProps, 'children' | 'flexDirection' | 'gap'> {
  title?: React.ReactNode;
  titlePrefix?: string;
  titleColor?: string;
  description?: React.ReactNode;
  descriptionColor?: string;
  headerRight?: React.ReactNode;
  tone?: PanelTone;
  headerGap?: number;
  bodyPaddingLeft?: number;
  bodyGap?: number;
  contentGap?: number;
  backgroundColor?: string;
  showBackground?: boolean;
  children: React.ReactNode;
}

const resolveToneColor = (tone: PanelTone): string => {
  switch (tone) {
    case 'accent':
      return theme.text.accent;
    case 'primary':
      return theme.text.primary;
    case 'info':
      return theme.status.info;
    case 'success':
      return theme.status.success;
    case 'warning':
      return theme.status.warning;
    case 'error':
      return theme.status.error;
    case 'muted':
    case 'default':
    default:
      return theme.text.muted;
  }
};

export const PanelSection: React.FC<PanelSectionProps> = ({
  title,
  titlePrefix,
  titleColor,
  description,
  descriptionColor,
  headerRight,
  tone = 'default',
  headerGap = 1,
  bodyPaddingLeft = 0,
  bodyGap = 0,
  contentGap,
  backgroundColor = colors.bgLight,
  showBackground = true,
  children,
  ...boxProps
}) => {
  const { paddingTop, paddingBottom, paddingY, ...restBoxProps } = boxProps;
  const toneColor = resolveToneColor(tone);
  const showHeader = Boolean(title || description || headerRight || titlePrefix);
  const resolvedGap = contentGap ?? (showHeader ? 1 : 0);
  const resolvedBackground = showBackground ? backgroundColor : undefined;
  const resolvedPaddingTop = paddingTop ?? paddingY ?? 1;
  const resolvedPaddingBottom = paddingBottom ?? paddingY ?? 1;

  const renderHeaderTitle = () => {
    if (!title) return null;
    if (typeof title === 'string') {
      return (
        <Text color={titleColor ?? theme.text.primary} bold>
          {title}
        </Text>
      );
    }
    return title;
  };

  const renderHeaderRight = () => {
    if (!headerRight) return null;
    if (typeof headerRight === 'string') {
      return <Text color={theme.text.muted}>{headerRight}</Text>;
    }
    return headerRight;
  };

  const renderDescription = () => {
    if (!description) return null;
    if (typeof description === 'string') {
      return <Text color={descriptionColor ?? theme.text.secondary}>{description}</Text>;
    }
    return description;
  };

  return (
    <Box
      flexDirection="column"
      gap={resolvedGap}
      backgroundColor={resolvedBackground}
      paddingTop={resolvedPaddingTop}
      paddingBottom={resolvedPaddingBottom}
      {...restBoxProps}
    >
      {showHeader && (
        <Box flexDirection="column">
          <Box flexDirection="row" gap={headerGap}>
            {titlePrefix && <Text color={toneColor}>{titlePrefix}</Text>}
            {renderHeaderTitle()}
            <Box flexGrow={1} />
            {renderHeaderRight()}
          </Box>
          {description && <Box paddingLeft={titlePrefix ? 2 : 0}>{renderDescription()}</Box>}
        </Box>
      )}
      <Box flexDirection="column" paddingLeft={bodyPaddingLeft} gap={bodyGap}>
        {children}
      </Box>
    </Box>
  );
};
