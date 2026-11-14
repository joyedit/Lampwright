using System.Collections.Generic;
using Vintagestory.API.Client;
using Vintagestory.API.Common;
using Vintagestory.API.Config;
using Vintagestory.API.Server;

namespace Lampwright;

/// <summary>
/// Makes the worn Lampwright's Belt emit light.
///
/// Vintage Story does not light the player from clothing slots. EntityPlayer.LightHsv
/// reads exactly two slots - RightHandItemSlot and LeftHandItemSlot - which is why the
/// vanilla temporal gear amulet ships a lightHsv that does nothing while worn.
///
/// The same property has a public setter that stores to a private baseLightHsv field,
/// and the getter merges that field with hand light via ColorUtil.MergeLightHSV. So
/// assigning to it is enough: no Harmony patch, and a torch in hand still works
/// alongside the belt rather than cancelling it.
///
/// SystemRenderPlayerEffects then picks every entity within 120 blocks whose
/// LightHsv[2] > 0 and feeds it to the shaders as a moving point light. Nothing is
/// baked into chunk lighting, so there is no relight cost and the glow lands on the
/// wearer's own model as well as the terrain around them.
///
/// The colour is never hardcoded here: it is read back off the collectible, so the
/// lightHsvByType block in itemtypes/lampbelt.json is the single source of truth and
/// new colour variants need no code change.
/// </summary>
public class LampwrightModSystem : ModSystem
{
	/// <summary>
	/// LightHsv is a plain instance field and is never sent over the wire, so the
	/// server publishes the belt's [hue, sat, brightness] here and each client applies
	/// the light locally. Without this, a wearer would be the only one who ever saw
	/// their own belt lit.
	/// </summary>
	public const string LightAttribute = "lampwrightLight";

	private const string BeltDomain = "lampwright";
	private const string BeltPrefix = "lampbelt";

	private ICoreServerAPI sapi;
	private ICoreClientAPI capi;

	// What this client last wrote per entity, so the light is only assigned on a change.
	// The getter cannot be used for this test: it returns hand light merged in, so a
	// wearer holding a torch would never read back the value that was set.
	private readonly Dictionary<long, byte[]> applied = new();

	/// <summary>
	/// LampbeltWearable stands in for the stock Wearable behaviour so the belt is never
	/// born randomly tattered - see that class for why. Registered here because a
	/// collectible behaviour has to be known by name before the itemtypes are parsed.
	/// </summary>
	public override void Start(ICoreAPI api)
	{
		api.RegisterCollectibleBehaviorClass("LampbeltWearable", typeof(LampbeltWearable));
	}

	public override void StartServerSide(ICoreServerAPI api)
	{
		sapi = api;
		api.Event.RegisterGameTickListener(OnServerTick, 500);
	}

	public override void StartClientSide(ICoreClientAPI api)
	{
		capi = api;
		api.Event.RegisterGameTickListener(OnClientTick, 250);
	}

	private void OnServerTick(float dt)
	{
		foreach (IPlayer player in sapi.World.AllOnlinePlayers)
		{
			EntityPlayer entity = player.Entity;
			if (entity == null) continue;   // connected but not yet spawned in

			byte[] hsv = WornBeltLight(player, sapi.World);
			byte[] published = entity.WatchedAttributes.GetBytes(LightAttribute);

			if (SameLight(hsv, published)) continue;

			if (hsv == null) entity.WatchedAttributes.RemoveAttribute(LightAttribute);
			else entity.WatchedAttributes.SetBytes(LightAttribute, hsv);
			entity.WatchedAttributes.MarkPathDirty(LightAttribute);
		}
	}

	private void OnClientTick(float dt)
	{
		IPlayer self = capi.World.Player;

		foreach (IPlayer player in capi.World.AllOnlinePlayers)
		{
			EntityPlayer entity = player.Entity;
			if (entity == null) continue;

			// For everyone else the synced value is the only thing this client can know.
			// For the player at this keyboard the character inventory is local, so read
			// it directly and skip the server round trip - otherwise equipping the belt
			// would visibly lag by up to half a second.
			byte[] hsv = player == self
				? WornBeltLight(player, capi.World)
				: entity.WatchedAttributes.GetBytes(LightAttribute);

			if (applied.TryGetValue(entity.EntityId, out byte[] was) && SameLight(was, hsv)) continue;

			entity.LightHsv = hsv;
			applied[entity.EntityId] = hsv;
		}
	}

	/// <summary>
	/// The lightHsv of the belt in the player's clothing slots, or null if none is worn.
	/// </summary>
	private static byte[] WornBeltLight(IPlayer player, IWorldAccessor world)
	{
		IInventory inv = player.InventoryManager?.GetOwnInventory(GlobalConstants.characterInvClassName);
		if (inv == null) return null;

		// Walking all ~15 clothing slots rather than indexing EnumCharacterDressType.Waist:
		// same cost at this tick rate, and it keeps working if the slot layout shifts or
		// another mod introduces a second belt-ish slot.
		for (int i = 0; i < inv.Count; i++)
		{
			ItemStack stack = inv[i]?.Itemstack;
			AssetLocation code = stack?.Collectible?.Code;
			if (code == null || code.Domain != BeltDomain || !code.Path.StartsWith(BeltPrefix, System.StringComparison.Ordinal)) continue;

			byte[] hsv = stack.Collectible.GetLightHsv(world.BlockAccessor, null, stack);
			if (hsv != null && hsv[2] > 0) return hsv;
		}

		return null;
	}

	private static bool SameLight(byte[] a, byte[] b)
	{
		if (a == null || b == null) return a == null && b == null;
		return a.Length == b.Length && a[0] == b[0] && a[1] == b[1] && a[2] == b[2];
	}
}
