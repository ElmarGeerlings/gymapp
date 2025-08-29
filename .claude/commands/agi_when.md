---
description: Create or modify slash commands based on user requirements
argument-hint: <command-name> <description-of-what-it-should-do>
---

# Parse arguments for the new command
COMMAND_NAME=$1
REQUIREMENTS="${@:2}"

# If no arguments provided, ask for them
if [ -z "$COMMAND_NAME" ]; then
  echo "Please provide: <command-name> <description-of-what-it-should-do>"
  echo "Example: /agi_when new-feature 'create a command that generates test files for components'"
  exit 1
fi

# Step 1: Research existing slash commands for patterns
echo "📚 Studying existing slash commands to understand patterns..."

Use researcher to analyze @.claude/commands folder:
- Read 3-4 existing command files to understand structure
- Identify common patterns and conventions
- Note the YAML frontmatter format (description, argument-hint)
- Understand how arguments are handled ($ARGUMENTS, $1, $2, etc.)
- Study how agents are used (researcher, executioner, etc.)

# Step 2: Fetch and understand slash command documentation
echo "📖 Learning from official documentation..."

Use WebFetch to get slash command documentation:
- Fetch https://docs.anthropic.com/en/docs/claude-code/slash-commands
- Understand the command structure requirements
- Learn about available features and limitations
- Note best practices for command creation

# Step 3: Design the new command based on requirements
echo "🎨 Designing command: $COMMAND_NAME"

Based on research and user requirements: "$REQUIREMENTS"

Design the command structure:
- Determine if it needs arguments and what format
- Decide which agents to use (researcher, executioner, or both)
- Plan the command flow and steps
- Consider if it needs todolists, branches, or commits
- Determine if it should be cyclic (like goalv2) or linear

# Step 4: Create or modify the command file
echo "✍️ Creating/modifying @.claude/commands/${COMMAND_NAME}.md"

Generate the command file with:
- Proper YAML frontmatter
  - description: concise description of what the command does
  - argument-hint: show expected arguments (if any)
- Clear argument parsing (if needed)
- Well-structured command logic
- Appropriate use of agents
- Clear instructions for each step
- Any necessary safety checks or validations

Example patterns to consider:
- Simple execution: Direct bash commands or single agent use
- Research-first: Use researcher to understand before acting
- Cyclic pattern: Like goalv2/port with alternating modes
- Multi-step process: Like port_to_raddbg with specific phases
- Tool-specific: Commands that focus on specific tools

# Step 5: Validate and test the command
echo "✅ Validating the new command..."

Ensure the command:
- Has valid markdown structure
- Includes proper YAML frontmatter
- Handles arguments correctly
- Uses agents appropriately
- Follows existing command conventions
- Is clear and unambiguous in instructions
- Includes error handling where needed

# Step 6: Provide usage instructions
echo "📝 Command created successfully!"

Show the user:
- How to use the new command: /command-name [arguments]
- What the command will do when executed
- Any important notes or limitations
- Suggest testing with a simple case first

# Common command patterns from @.claude/commands:

## Pattern 1: Simple task executor
```
---
description: Do a specific task
argument-hint: [optional arguments]
---
Execute the task using appropriate tools
```

## Pattern 2: Research and execute
```
---
description: Research then implement
argument-hint: <target>
---
TARGET=$1
Use researcher to understand $TARGET
Use executioner to implement changes
```

## Pattern 3: Cyclic workflow (like goalv2)
```
---
description: Iterative task completion
argument-hint: <goal>
---
Create todolist
Cycle through: Research → Execute → Adjust
Maintain todolist throughout
```

## Pattern 4: Multi-codebase operations (like port_to_raddbg)
```
---
description: Work across multiple codebases
argument-hint: <source> <destination>
---
Research source
Research destination
Research integration points
Execute changes
Verify quality
```

Think carefully about what kind of command pattern best fits "$REQUIREMENTS"!