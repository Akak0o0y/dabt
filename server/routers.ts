import { COOKIE_NAME } from "@shared/const";
import { z } from "zod";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";
import { evaluateDabt, getDabtComplianceMap } from "./dabt";

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),
  dabt: router({
    evaluate: publicProcedure
      .input(
        z.object({
          document: z.string().min(1).max(100_000),
          agentId: z.string().max(128).optional(),
          purpose: z.string().max(256).optional(),
          lawfulBasis: z.string().max(128).optional(),
          crossBorder: z.boolean().optional(),
          sector: z.string().max(128).optional(),
          eventType: z.string().max(128).optional(),
          agentAuthorised: z.boolean().optional(),
          requiresMinimisation: z.boolean().optional(),
        }),
      )
      .mutation(({ input }) => evaluateDabt(input)),
    complianceMap: publicProcedure.query(() => getDabtComplianceMap()),
  }),

  // TODO: add feature routers here, e.g.
  // todo: router({
  //   list: protectedProcedure.query(({ ctx }) =>
  //     db.getUserTodos(ctx.user.id)
  //   ),
  // }),
});

export type AppRouter = typeof appRouter;
