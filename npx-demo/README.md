# AI Flow Architect — npx Demo

**Instant dual-model adversarial code audit. Two AI models audit your code independently. When they disagree, you see exactly why.**

## Try it now

```bash
npx ai-flow-architect-demo
```

No API key required. No installation. See a full dual-model adversarial audit in 3 seconds.

## What you'll see

The demo runs the built-in `ai-flow example` command, which audits a sample AI-generated code snippet with:

- **Brain 1 (Chief Architect)**: Reviews the code for correctness, completeness, and hallucinations
- **Brain 2 (Quality Arbiter)**: Independently audits the same code with 3 arbiter models
- **Adversarial Testing**: An opponent model generates attack examples to stress-test findings
- **Trust Report**: A structured verdict with confidence score, findings, risks, and evidence chain

## After the demo

```bash
# Install locally to audit your own code
pip install --user ai-flow-architect && ai-flow init

# Or try the web Playground
# https://ai-flow-architect.github.io/playground
```

## Links

- [GitHub](https://github.com/HANAKO/ai-flow-architect)
- [Playground](https://ai-flow-architect.github.io/playground)
- [Documentation](https://github.com/HANAKO/ai-flow-architect#readme)

## License

MIT
