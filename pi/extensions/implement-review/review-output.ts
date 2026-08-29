import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const ReviewSchema = Type.Object(
	{
		findings: Type.Array(
			Type.Object(
				{
					title: Type.String(),
					severity: Type.Union([Type.Literal("blocking"), Type.Literal("non-blocking")]),
					file: Type.Optional(Type.String()),
					detail: Type.String(),
				},
				{ additionalProperties: false },
			),
		),
	},
	{ additionalProperties: false },
);

export default function reviewOutputExtension(pi: ExtensionAPI) {
	pi.registerTool({
		name: "submit_review",
		label: "Submit review",
		description:
			"Submit the complete code review. Call exactly once after vetting every finding. Use blocking only for findings that must be fixed before approval.",
		parameters: ReviewSchema,
		async execute(_toolCallId, params) {
			return {
				content: [{ type: "text", text: `Accepted ${params.findings.length} structured finding(s).` }],
				details: params,
			};
		},
	});
}
