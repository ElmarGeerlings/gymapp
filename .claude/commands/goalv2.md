---
description: Execute a goal with systematic 3-mode alternating pattern
argument-hint: [goal description]
---

$GOAL=$ARGUMENTS

# Check if we're already on a specialized branch, create one if not
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == "develop" ]]; then
  git checkout -b "goal-$(echo "$GOAL" | tr '[:upper:] ' '[:lower:]-' | head -c 50)"
else
  echo "Already on specialized branch: $CURRENT_BRANCH"
fi

# Initial research phase
Use researcher agent to understand the current state of the project for: $GOAL
- Analyze existing codebase and structure
- Identify what needs to be done to achieve the goal
- Understand dependencies and constraints

# CRITICAL: Create and maintain a comprehensive todolist!
# The todolist is your PRIMARY tracking mechanism - keep it updated CONSTANTLY

# Create initial todolist following the 3-mode pattern
# IMPORTANT: Use TodoWrite tool to create a detailed todolist NOW
# This todolist MUST be kept current throughout the entire process
Write a todolist that alternates between these 3 modes:

Mode 1 - Research Changes:
  Use researcher to figure out exact necessary changes for the task
  - Mark current research task as in_progress in todolist
  - Analyze requirements
  - Identify files and components to modify
  - Plan implementation approach
  - Update todolist with specific implementation tasks discovered

Mode 2 - Execute Changes:
  Use executioner to implement the researched changes
  - Mark current execution task as in_progress in todolist
  - Make precise code modifications
  - Follow the plan from research phase
  - Ensure quality and correctness
  - Mark completed tasks as done IMMEDIATELY after finishing

Mode 3 - Adjust Todos & Commit:
  MANDATORY: Update todolist to reflect current state
  - Commit current progress with descriptive message
  - Mark ALL completed items as done in todolist
  - Add ANY new tasks discovered during implementation
  - Remove obsolete tasks that are no longer needed
  - Ensure todolist accurately reflects remaining work
  - Maintain the 3-mode alternating pattern for remaining tasks
  - NEVER skip this todolist update - it's CRITICAL for tracking

# Example todolist structure:
1. Research: Analyze requirements for feature X
2. Execute: Implement feature X based on research
3. Adjust & Commit: Commit progress and update todos
4. Research: Investigate integration points for feature Y
5. Execute: Implement feature Y integration
6. Adjust & Commit: Commit progress and review remaining tasks
...continue pattern...

# Final quality check and commit
At the end, use researcher to verify the quality of work:
- Ensure all aspects of $GOAL are achieved
- Check for consistency and completeness
- Identify any issues or improvements
- Make final commit with summary of completed goal

Think carefully! Systematically achieve $GOAL through alternating research, execution, and adjustment cycles!

REMEMBER: The todolist is your primary tool for success - keep it updated CONSTANTLY, not just at adjustment phases!